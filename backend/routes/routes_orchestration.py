"""Multi-Agent Orchestration — Agent-to-agent delegation and workflow chains.

Supports sequential chains, parallel fan-out, and conditional routing between agents.
"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class OrchestrationStep(BaseModel):
    step_id: str = ""
    agent_id: str
    prompt_template: str = "{input}"
    depends_on: List[str] = []
    condition: str = ""


class CreateOrchestration(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    steps: List[OrchestrationStep]
    execution_mode: str = "sequential"


class RunOrchestrationRequest(BaseModel):
    input_text: str = Field(..., min_length=1)
    context: Dict = {}


def register_orchestration_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/orchestrations")
    async def create_orchestration(ws_id: str, data: CreateOrchestration, request: Request):
        user = await _authed_user(request, ws_id)
        orch_id = f"orch_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        steps = []
        for i, s in enumerate(data.steps):
            steps.append({
                "step_id": s.step_id or f"step_{i}",
                "agent_id": s.agent_id,
                "prompt_template": s.prompt_template,
                "depends_on": s.depends_on,
                "condition": s.condition,
            })
        orch = {
            "orchestration_id": orch_id, "workspace_id": ws_id, "name": data.name,
            "description": data.description, "execution_mode": data.execution_mode,
            "steps": steps, "step_count": len(steps),
            "created_by": user["user_id"], "run_count": 0,
            "created_at": now, "updated_at": now,
        }
        await db.orchestrations.insert_one(orch)
        orch.pop("_id", None)
        return orch

    @api_router.get("/workspaces/{ws_id}/orchestrations")
    async def list_orchestrations(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        orchs = await db.orchestrations.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"orchestrations": orchs}

    @api_router.get("/workspaces/{ws_id}/orchestrations/{orch_id}")
    async def get_orchestration(ws_id: str, orch_id: str, request: Request):
        await _authed_user(request, ws_id)
        orch = await db.orchestrations.find_one({"orchestration_id": orch_id, "workspace_id": ws_id}, {"_id": 0})
        if not orch:
            raise HTTPException(404, "Orchestration not found")
        return orch

    @api_router.delete("/workspaces/{ws_id}/orchestrations/{orch_id}")
    async def delete_orchestration(ws_id: str, orch_id: str, request: Request):
        await _authed_user(request, ws_id)
        await db.orchestrations.delete_one({"orchestration_id": orch_id, "workspace_id": ws_id})
        return {"deleted": orch_id}

    @api_router.post("/workspaces/{ws_id}/orchestrations/{orch_id}/run")
    async def run_orchestration(ws_id: str, orch_id: str, data: RunOrchestrationRequest, request: Request, background_tasks: BackgroundTasks):
        user = await _authed_user(request, ws_id)
        orch = await db.orchestrations.find_one({"orchestration_id": orch_id, "workspace_id": ws_id}, {"_id": 0})
        if not orch:
            raise HTTPException(404, "Orchestration not found")

        run_id = f"orun_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "run_id": run_id, "orchestration_id": orch_id, "orchestration_name": orch["name"],
            "workspace_id": ws_id, "started_by": user["user_id"],
            "input_text": data.input_text, "context": data.context,
            "status": "running", "step_results": [], "final_output": "",
            "started_at": now, "completed_at": None,
        }
        await db.orchestration_runs.insert_one(run)
        run.pop("_id", None)

        await db.orchestrations.update_one({"orchestration_id": orch_id}, {"$inc": {"run_count": 1}})
        background_tasks.add_task(_execute_orchestration, db, run_id, orch, data.input_text, data.context, ws_id)
        return run

    @api_router.get("/workspaces/{ws_id}/orchestrations/{orch_id}/runs")
    async def list_orchestration_runs(ws_id: str, orch_id: str, request: Request):
        await _authed_user(request, ws_id)
        runs = await db.orchestration_runs.find(
            {"orchestration_id": orch_id, "workspace_id": ws_id},
            {"_id": 0, "run_id": 1, "status": 1, "started_at": 1, "completed_at": 1, "final_output": 1}
        ).sort("started_at", -1).limit(20).to_list(20)
        return {"runs": runs}

    @api_router.get("/workspaces/{ws_id}/orchestration-runs/{run_id}")
    async def get_orchestration_run(ws_id: str, run_id: str, request: Request):
        await _authed_user(request, ws_id)
        run = await db.orchestration_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run


async def _execute_orchestration(db, run_id, orch, input_text, context, ws_id):
    """Execute orchestration steps sequentially or in parallel."""
    from agent_knowledge_retrieval import retrieve_training_knowledge
    steps = orch.get("steps") or []
    mode = orch.get("execution_mode", "sequential")
    step_outputs = {}
    step_results = []

    try:
        if mode == "parallel":
            tasks = []
            for step in steps:
                prompt = step["prompt_template"].replace("{input}", input_text)
                for key, val in context.items():
                    prompt = prompt.replace(f"{{{key}}}", str(val))
                tasks.append(_run_single_step(db, step, prompt, ws_id))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for step, result in zip(steps, results):
                if isinstance(result, Exception):
                    step_results.append({"step_id": step["step_id"], "agent_id": step["agent_id"], "status": "failed", "error": str(result), "output": ""})
                else:
                    step_outputs[step["step_id"]] = result
                    step_results.append({"step_id": step["step_id"], "agent_id": step["agent_id"], "status": "completed", "output": result[:2000]})
        else:
            current_input = input_text
            for step in steps:
                # Check condition
                if step.get("condition"):
                    if not _eval_condition(step["condition"], step_outputs, current_input):
                        step_results.append({"step_id": step["step_id"], "agent_id": step["agent_id"], "status": "skipped", "output": ""})
                        continue

                prompt = step["prompt_template"].replace("{input}", current_input)
                for dep_id in step.get("depends_on") or []:
                    if dep_id in step_outputs:
                        prompt = prompt.replace(f"{{{dep_id}}}", step_outputs[dep_id])
                for key, val in context.items():
                    prompt = prompt.replace(f"{{{key}}}", str(val))

                try:
                    output = await _run_single_step(db, step, prompt, ws_id)
                    step_outputs[step["step_id"]] = output
                    current_input = output
                    step_results.append({"step_id": step["step_id"], "agent_id": step["agent_id"], "status": "completed", "output": output[:2000]})
                except Exception as e:
                    step_results.append({"step_id": step["step_id"], "agent_id": step["agent_id"], "status": "failed", "error": str(e), "output": ""})
                    break

        final_output = step_outputs.get(steps[-1]["step_id"], "") if steps else ""
        now = datetime.now(timezone.utc).isoformat()
        await db.orchestration_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "completed", "step_results": step_results, "final_output": final_output[:5000], "completed_at": now}}
        )
    except Exception as e:
        await db.orchestration_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed", "error": str(e), "step_results": step_results, "completed_at": datetime.now(timezone.utc).isoformat()}}
        )


async def _run_single_step(db, step, prompt, ws_id):
    """Run a single step using the agent's knowledge retrieval."""
    agent_id = step["agent_id"]
    from agent_knowledge_retrieval import retrieve_training_knowledge
    knowledge = await retrieve_training_knowledge(db, agent_id, prompt, max_chunks=5, max_tokens=2000)
    if knowledge:
        return f"[Agent {agent_id} with knowledge context]\n{knowledge}\n\nBased on the above knowledge, here is the response to: {prompt[:500]}"
    return f"[Agent {agent_id}] Processing: {prompt[:500]}\n\nNo specific training knowledge available for this query."


def _eval_condition(condition, outputs, current_input):
    """Simple condition evaluation."""
    try:
        if "contains:" in condition:
            keyword = condition.split("contains:")[-1].strip().lower()
            return keyword in current_input.lower()
        if "length>" in condition:
            threshold = int(condition.split("length>")[-1].strip())
            return len(current_input) > threshold
        return True
    except Exception:
        return True
