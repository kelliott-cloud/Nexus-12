"""Prompt Optimization Pipeline — Build datasets & optimize agent system prompts.

Uses Claude to evaluate dataset quality, generate improved examples,
and create optimized system prompts from agent knowledge.
Note: This is AI-powered prompt optimization, not traditional model fine-tuning.
No model weights are modified.
"""
import uuid
import logging
import json
import os
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from nexus_utils import sanitize_filename
from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)


class CreateDataset(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source: str = "knowledge"
    include_conversations: bool = True
    include_knowledge: bool = True
    min_quality_score: float = 0.5
    max_examples: int = 500


class CreateFineTuneJob(BaseModel):
    dataset_id: str
    base_model: str = "claude-sonnet-4-5-20250929"
    provider: str = "anthropic"
    hyperparameters: dict = {}


def register_finetune_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access, sanitize_filename
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/finetune/datasets")
    async def create_dataset(ws_id: str, agent_id: str, data: CreateDataset, request: Request):
        user = await _authed_user(request, ws_id)
        dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()

        examples = []

        if data.include_knowledge:
            chunks = await db.agent_knowledge.find(
                {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True},
                 "quality_score": {"$gte": data.min_quality_score}},
                {"_id": 0, "content": 1, "topic": 1, "category": 1, "summary": 1}
            ).sort("quality_score", -1).limit(data.max_examples).to_list(data.max_examples)

            agent = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0, "system_prompt": 1, "name": 1})
            sys_prompt = (agent or {}).get("system_prompt", "You are a helpful assistant.")

            for chunk in chunks:
                topic = chunk.get("topic", "general")
                content = chunk.get("content", "")
                summary = chunk.get("summary", content[:100])
                examples.append({
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"Tell me about {topic}: {summary}"},
                        {"role": "assistant", "content": content},
                    ]
                })

        if data.include_conversations:
            conv_chunks = await db.agent_knowledge.find(
                {"agent_id": agent_id, "source.type": "conversation", "flagged": {"$ne": True}},
                {"_id": 0, "content": 1}
            ).limit(data.max_examples // 2).to_list(data.max_examples // 2)

            if "agent" not in dir():
                agent = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0, "system_prompt": 1})
            sys_prompt = (agent or {}).get("system_prompt", "You are a helpful assistant.")

            for chunk in conv_chunks:
                content = chunk.get("content", "")
                if "\n\nA: " in content:
                    parts = content.split("\n\nA: ", 1)
                    q = parts[0].replace("Q: ", "", 1).strip()
                    a = parts[1].strip()
                    examples.append({
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": q},
                            {"role": "assistant", "content": a},
                        ]
                    })

        dataset = {
            "dataset_id": dataset_id, "agent_id": agent_id, "workspace_id": ws_id,
            "name": data.name, "source": data.source,
            "example_count": len(examples), "examples": examples,
            "min_quality_score": data.min_quality_score,
            "format": "chat_messages",
            "created_by": user["user_id"],
            "created_at": now, "updated_at": now,
        }
        await db.finetune_datasets.insert_one(dataset)
        dataset.pop("_id", None)
        dataset.pop("examples", None)
        dataset["example_count"] = len(examples)
        return dataset

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/finetune/datasets")
    async def list_datasets(ws_id: str, agent_id: str, request: Request):
        await _authed_user(request, ws_id)
        datasets = await db.finetune_datasets.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "dataset_id": 1, "name": 1, "example_count": 1, "format": 1, "created_at": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"datasets": datasets}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/finetune/datasets/{dataset_id}/export")
    async def export_dataset_jsonl(ws_id: str, agent_id: str, dataset_id: str, request: Request):
        await _authed_user(request, ws_id)
        dataset = await db.finetune_datasets.find_one(
            {"dataset_id": dataset_id, "agent_id": agent_id}, {"_id": 0, "examples": 1}
        )
        if not dataset:
            raise HTTPException(404, "Dataset not found")
        lines = [json.dumps(ex) for ex in dataset.get("examples") or []]
        content = "\n".join(lines)
        return PlainTextResponse(content, media_type="application/jsonl",
                                 headers={"Content-Disposition": f"attachment; filename={sanitize_filename(dataset_id)}.jsonl"})

    @api_router.delete("/workspaces/{ws_id}/agents/{agent_id}/finetune/datasets/{dataset_id}")
    async def delete_dataset(ws_id: str, agent_id: str, dataset_id: str, request: Request):
        await _authed_user(request, ws_id)
        await db.finetune_datasets.delete_one({"dataset_id": dataset_id, "agent_id": agent_id})
        return {"deleted": dataset_id}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/finetune/jobs")
    async def create_finetune_job(ws_id: str, agent_id: str, data: CreateFineTuneJob, request: Request, background_tasks: BackgroundTasks):
        user = await _authed_user(request, ws_id)
        dataset = await db.finetune_datasets.find_one(
            {"dataset_id": data.dataset_id, "agent_id": agent_id},
            {"_id": 0, "dataset_id": 1, "name": 1, "example_count": 1}
        )
        if not dataset:
            raise HTTPException(404, "Dataset not found")

        job_id = f"ftjob_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "job_id": job_id, "agent_id": agent_id, "workspace_id": ws_id,
            "dataset_id": data.dataset_id, "dataset_name": dataset.get("name", ""),
            "example_count": dataset.get("example_count", 0),
            "base_model": data.base_model, "provider": data.provider,
            "hyperparameters": data.hyperparameters,
            "status": "running", "progress": 0,
            "evaluation_results": None,
            "optimized_prompt": None,
            "fine_tuned_model": None,
            "created_by": user["user_id"],
            "created_at": now, "updated_at": now,
        }
        await db.finetune_jobs.insert_one(job)
        job.pop("_id", None)

        background_tasks.add_task(_run_finetune_job, db, job_id, agent_id, data.dataset_id, ws_id)
        return job

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/finetune/jobs")
    async def list_finetune_jobs(ws_id: str, agent_id: str, request: Request):
        await _authed_user(request, ws_id)
        jobs = await db.finetune_jobs.find(
            {"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"jobs": jobs}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/finetune/jobs/{job_id}")
    async def get_finetune_job(ws_id: str, agent_id: str, job_id: str, request: Request):
        await _authed_user(request, ws_id)
        job = await db.finetune_jobs.find_one({"job_id": job_id, "agent_id": agent_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/finetune/jobs/{job_id}/apply")
    async def apply_finetuned_model(ws_id: str, agent_id: str, job_id: str, request: Request):
        await _authed_user(request, ws_id)
        job = await db.finetune_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") != "completed":
            raise HTTPException(400, "Job not completed yet")

        optimized_prompt = job.get("optimized_prompt", "")
        if not optimized_prompt:
            raise HTTPException(400, "No optimized prompt available")

        await db.nexus_agents.update_one(
            {"agent_id": agent_id},
            {"$set": {
                "system_prompt": optimized_prompt,
                "fine_tuned": True,
                "fine_tune_job_id": job_id,
                "fine_tune_model": job.get("base_model"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {"applied": True, "agent_id": agent_id, "job_id": job_id}


async def _run_finetune_job(db, job_id, agent_id, dataset_id, ws_id):
    """Background task: Use Claude to evaluate dataset and generate optimized system prompt."""
    try:
        import httpx
        from key_resolver import get_integration_key

        api_key = await get_integration_key(db, "ANTHROPIC_API_KEY")
        if not api_key:
            await db.finetune_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": "No Anthropic API key configured"}}
            )
            return

        dataset = await db.finetune_datasets.find_one(
            {"dataset_id": dataset_id}, {"_id": 0, "examples": 1}
        )
        examples = dataset.get("examples") or [] if dataset else []
        if not examples:
            await db.finetune_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": "Dataset is empty"}}
            )
            return

        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id},
            {"_id": 0, "name": 1, "system_prompt": 1, "skills": 1, "persona": 1}
        )
        agent_name = (agent or {}).get("name", "Agent")
        current_prompt = (agent or {}).get("system_prompt", "You are a helpful assistant.")
        skills = (agent or {}).get("skills") or []

        # Phase 1: Evaluate dataset quality (30%)
        await db.finetune_jobs.update_one(
            {"job_id": job_id}, {"$set": {"progress": 10, "status": "evaluating_dataset"}}
        )

        sample_examples = examples[:15]
        examples_text = "\n\n".join([
            f"Example {i+1}:\nUser: {ex['messages'][-2]['content'][:200]}\nAssistant: {ex['messages'][-1]['content'][:300]}"
            for i, ex in enumerate(sample_examples) if len(ex.get("messages") or []) >= 2
        ])

        async def _call_claude(system_msg, user_prompt):
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post("https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-5-20250929", "max_tokens": 4096,
                          "system": system_msg, "messages": [{"role": "user", "content": user_prompt}]})
                if resp.status_code != 200:
                    raise Exception(f"Anthropic API error: {resp.status_code}")
                return resp.json()["content"][0]["text"]

        eval_response = await _call_claude(
            "You are an expert AI training data evaluator. Analyze training examples and provide structured feedback.",
            f"""Evaluate these training examples for agent "{agent_name}".

Current system prompt: {current_prompt[:500]}

Training examples:
{examples_text}

Provide a JSON evaluation with:
{{
  "overall_quality": 0-100,
  "consistency_score": 0-100,
  "coverage_score": 0-100,
  "tone_alignment": 0-100,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "improvement_suggestions": ["suggestion1", "suggestion2"]
}}

Return ONLY the JSON, no other text."""
        )
        eval_response = eval_response

        evaluation = {}
        try:
            clean = eval_response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            evaluation = json.loads(clean)
        except Exception:
            evaluation = {
                "overall_quality": 70, "consistency_score": 65,
                "coverage_score": 60, "tone_alignment": 75,
                "strengths": ["Dataset has training examples"],
                "weaknesses": ["Could not parse detailed evaluation"],
                "improvement_suggestions": ["Add more diverse examples"]
            }

        await db.finetune_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"progress": 30, "evaluation_results": evaluation}}
        )

        # Phase 2: Generate optimized system prompt (70%)
        await db.finetune_jobs.update_one(
            {"job_id": job_id}, {"$set": {"progress": 50, "status": "generating_prompt"}}
        )

        skills_text = ", ".join(skills[:20]) if skills else "general knowledge"
        topics_covered = set()
        for ex in examples[:30]:
            msgs = ex.get("messages") or []
            if len(msgs) >= 2:
                user_msg = msgs[-2].get("content", "")
                for word in user_msg.split()[:5]:
                    if len(word) > 3:
                        topics_covered.add(word.lower())

        optimized_prompt = await _call_claude(
            "You are an expert AI prompt engineer. Create optimized system prompts that maximize agent performance based on training data analysis.",
            f"""Based on the training data analysis, create an optimized system prompt for agent "{agent_name}".

Current prompt: {current_prompt}

Agent skills: {skills_text}
Dataset size: {len(examples)} examples
Quality scores: overall={evaluation.get('overall_quality', 70)}, consistency={evaluation.get('consistency_score', 65)}
Key strengths: {', '.join(evaluation.get('strengths', []))}
Areas to improve: {', '.join(evaluation.get('weaknesses', []))}

Sample topics from training data: {', '.join(list(topics_covered)[:15])}

Create an optimized system prompt that:
1. Preserves the core identity and purpose
2. Incorporates patterns from the training data
3. Addresses identified weaknesses
4. Enhances response quality and consistency
5. Is clear, concise, and actionable

Return ONLY the optimized system prompt text, nothing else. No markdown formatting."""
        )

        await db.finetune_jobs.update_one(
            {"job_id": job_id}, {"$set": {"progress": 80}}
        )

        # Phase 3: Complete
        now = datetime.now(timezone.utc).isoformat()
        await db.finetune_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "optimized_prompt": optimized_prompt.strip(),
                "evaluation_results": evaluation,
                "completed_at": now,
                "updated_at": now,
            }}
        )
        logger.info(f"Fine-tune job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Fine-tune job {job_id} failed: {e}")
        await db.finetune_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "failed", "error": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
