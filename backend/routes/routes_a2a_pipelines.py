"""A2A Pipeline Routes — CRUD, triggering, run management, templates, analytics."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



class A2AStepCreate(BaseModel):
    name: str = ""
    agent_id: str = ""
    prompt_template: str = "{trigger_payload}"
    system_prompt_override: Optional[str] = None
    tools_allowed: List[str] = []
    tools_denied: List[str] = []
    temperature: float = 0.7
    max_tokens: int = 4096
    quality_gate: dict = {}
    routing: dict = {"type": "sequential"}
    timeout_sec: int = 120
    order: int = 0


class A2APipelineCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    steps: List[A2AStepCreate] = []
    settings: dict = {}
    triggers: List[dict] = []


def register_a2a_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    # ============ Pipeline CRUD ============

    @api_router.post("/workspaces/{ws_id}/a2a/pipelines")
    async def create_pipeline(ws_id: str, data: A2APipelineCreate, request: Request):
        user = await _authed_user(request, ws_id)
        pipeline_id = f"a2a_pip_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        steps = []
        for i, s in enumerate(data.steps):
            step = s.dict()
            if not step.get("step_id"):
                step["step_id"] = f"step_{i:03d}"
            steps.append(step)

        pipeline = {
            "pipeline_id": pipeline_id, "workspace_id": ws_id,
            "name": data.name, "description": data.description,
            "status": "draft", "steps": steps,
            "settings": {
                "max_total_cost_usd": data.settings.get("max_total_cost_usd", 5.0),
                "max_total_duration_sec": data.settings.get("max_total_duration_sec", 600),
                "max_retries_per_step": data.settings.get("max_retries_per_step", 3),
                "notification_channel_id": data.settings.get("notification_channel_id", ""),
                "on_failure": data.settings.get("on_failure", "pause_and_notify"),
                "enable_cost_tracking": data.settings.get("enable_cost_tracking", True),
                "context_window_strategy": data.settings.get("context_window_strategy", "rolling"),
                **(data.settings),
            },
            "triggers": data.triggers,
            "run_count": 0, "last_run_at": None,
            "created_by": user["user_id"], "created_at": now, "updated_at": now,
        }
        await db.a2a_pipelines.insert_one(pipeline)
        pipeline.pop("_id", None)
        return pipeline

    @api_router.get("/workspaces/{ws_id}/a2a/pipelines")
    async def list_pipelines(ws_id: str, request: Request, limit: int = 20):
        await _authed_user(request, ws_id)
        pipelines = await db.a2a_pipelines.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"pipelines": pipelines}

    @api_router.get("/a2a/pipelines/{pipeline_id}")
    async def get_pipeline(pipeline_id: str, request: Request):
        await get_current_user(request)
        p = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Pipeline not found")
        return p

    @api_router.put("/a2a/pipelines/{pipeline_id}")
    async def update_pipeline(pipeline_id: str, request: Request):
        user = await get_current_user(request)
        pipe = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"workspace_id": 1})
        if not pipe:
            raise HTTPException(404, "Pipeline not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, pipe["workspace_id"])
        body = await request.json()
        updates = {}
        for field in ["name", "description", "steps", "settings", "triggers"]:
            if field in body:
                updates[field] = body[field]
        updates["updated_at"] = now_iso()
        await db.a2a_pipelines.update_one({"pipeline_id": pipeline_id}, {"$set": updates})
        p = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": 0})
        return p

    @api_router.delete("/a2a/pipelines/{pipeline_id}")
    async def delete_pipeline(pipeline_id: str, request: Request):
        user = await get_current_user(request)
        pipe = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"workspace_id": 1})
        if not pipe:
            raise HTTPException(404, "Pipeline not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, pipe["workspace_id"])
        await db.a2a_pipelines.delete_one({"pipeline_id": pipeline_id})
        return {"deleted": True}

    @api_router.post("/a2a/pipelines/{pipeline_id}/activate")
    async def activate_pipeline(pipeline_id: str, request: Request):
        user = await get_current_user(request)
        pipe = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"workspace_id": 1})
        if not pipe:
            raise HTTPException(404, "Pipeline not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, pipe["workspace_id"])
        await db.a2a_pipelines.update_one({"pipeline_id": pipeline_id}, {"$set": {"status": "active", "updated_at": now_iso()}})
        return {"status": "active"}

    @api_router.post("/a2a/pipelines/{pipeline_id}/pause")
    async def pause_pipeline(pipeline_id: str, request: Request):
        user = await get_current_user(request)
        pipe = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"workspace_id": 1})
        if not pipe:
            raise HTTPException(404, "Pipeline not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, pipe["workspace_id"])
        await db.a2a_pipelines.update_one({"pipeline_id": pipeline_id}, {"$set": {"status": "paused", "updated_at": now_iso()}})
        return {"status": "paused"}

    # ============ Trigger & Run Management ============

    @api_router.post("/a2a/pipelines/{pipeline_id}/trigger")
    async def trigger_pipeline(pipeline_id: str, request: Request, background_tasks: BackgroundTasks):
        user = await get_current_user(request)
        pipeline = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": 0})
        if not pipeline:
            raise HTTPException(404, "Pipeline not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, pipeline["workspace_id"])

        body = {}
        try:
            body = await request.json()
        except Exception as e:
            logger.debug(f"Non-JSON body: {e}")

        run_id = f"a2a_run_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        run = {
            "run_id": run_id, "pipeline_id": pipeline_id,
            "workspace_id": pipeline["workspace_id"],
            "status": "running",
            "trigger_type": body.get("trigger_type", "manual"),
            "trigger_payload": body.get("payload", body.get("trigger_payload", "")),
            "current_step_id": None,
            "step_outputs": {},
            "total_cost_usd": 0, "total_tokens_in": 0, "total_tokens_out": 0, "total_duration_ms": 0,
            "started_at": now, "completed_at": None, "error": None, "pause_reason": None,
            "created_by": user.get("user_id", "system"), "created_at": now,
        }
        await db.a2a_runs.insert_one(run)
        run.pop("_id", None)

        await db.a2a_pipelines.update_one({"pipeline_id": pipeline_id}, {"$inc": {"run_count": 1}, "$set": {"last_run_at": now}})

        from a2a_engine import A2AEngine
        engine = A2AEngine(db)
        background_tasks.add_task(engine.execute_pipeline, run_id)

        return {"run_id": run_id, "status": "running"}

    @api_router.get("/a2a/pipelines/{pipeline_id}/runs")
    async def list_runs(pipeline_id: str, request: Request, limit: int = 20):
        await get_current_user(request)
        runs = await db.a2a_runs.find(
            {"pipeline_id": pipeline_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"runs": runs}

    @api_router.get("/a2a/runs/{run_id}")
    async def get_run(run_id: str, request: Request):
        await get_current_user(request)
        run = await db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @api_router.get("/a2a/runs/{run_id}/steps")
    async def get_run_steps(run_id: str, request: Request):
        await get_current_user(request)
        steps = await db.a2a_step_executions.find(
            {"run_id": run_id}, {"_id": 0}
        ).sort("started_at", 1).to_list(100)
        return {"steps": steps}

    @api_router.post("/a2a/runs/{run_id}/cancel")
    async def cancel_run(run_id: str, request: Request):
        await get_current_user(request)
        await db.a2a_runs.update_one({"run_id": run_id}, {"$set": {"status": "cancelled", "completed_at": now_iso()}})
        return {"status": "cancelled"}

    @api_router.post("/a2a/runs/{run_id}/resume")
    async def resume_run(run_id: str, request: Request, background_tasks: BackgroundTasks):
        await get_current_user(request)
        run = await db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run or run.get("status") != "paused":
            raise HTTPException(400, "Run is not paused")

        body = {}
        try:
            body = await request.json()
        except Exception as e:
            logger.debug(f"Non-JSON body: {e}")

        # If human provided output, store it
        if body.get("output"):
            current = run.get("current_step_id", "")
            await db.a2a_runs.update_one({"run_id": run_id}, {
                "$set": {f"step_outputs.{current}": {"output": body["output"], "quality_score": 1.0, "cost_usd": 0, "duration_ms": 0, "retries": 0}}
            })

        # Find next step
        pipeline = await db.a2a_pipelines.find_one({"pipeline_id": run["pipeline_id"]}, {"_id": 0})
        steps = pipeline.get("steps") or [] if pipeline else []
        current = run.get("current_step_id", "")
        next_step = None
        found_current = False
        for s in steps:
            if found_current:
                next_step = s.get("step_id")
                break
            if s.get("step_id") == current:
                found_current = True
                # Check routing
                routing = s.get("routing") or {}
                if routing.get("next_step_id"):
                    next_step = routing["next_step_id"]
                    break

        await db.a2a_runs.update_one({"run_id": run_id}, {"$set": {
            "status": "running", "pause_reason": None, "current_step_id": next_step,
        }})

        if next_step:
            from a2a_engine import A2AEngine
            engine = A2AEngine(db)
            background_tasks.add_task(engine.execute_pipeline, run_id)

        return {"status": "running", "next_step_id": next_step}

    # ============ Templates ============

    @api_router.get("/workspaces/{ws_id}/a2a/templates")
    async def get_templates(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        return {"templates": _builtin_templates()}

    # ============ Analytics ============

    @api_router.get("/workspaces/{ws_id}/a2a/analytics")
    async def a2a_analytics(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        total_runs = await db.a2a_runs.count_documents({"workspace_id": ws_id})
        completed = await db.a2a_runs.count_documents({"workspace_id": ws_id, "status": "completed"})
        failed = await db.a2a_runs.count_documents({"workspace_id": ws_id, "status": "failed"})

        pipeline_cost = [{"$match": {"workspace_id": ws_id}}, {"$group": {"_id": None, "total_cost": {"$sum": "$total_cost_usd"}, "avg_duration": {"$avg": "$total_duration_ms"}}}]
        agg = await db.a2a_runs.aggregate(pipeline_cost).to_list(1)
        stats = agg[0] if agg else {"total_cost": 0, "avg_duration": 0}
        stats.pop("_id", None)

        return {
            "total_runs": total_runs, "completed": completed, "failed": failed,
            "success_rate": round(completed / max(total_runs, 1) * 100, 1),
            "total_cost_usd": round(stats.get("total_cost", 0), 4),
            "avg_duration_ms": int(stats.get("avg_duration", 0) or 0),
        }


def _builtin_templates():
    return [
        {
            "template_id": "code_review", "name": "Code Review Pipeline",
            "description": "Security Agent → Quality Agent → Documentation Agent. Quality gate on security step.",
            "category": "development",
            "steps": [
                {"step_id": "step_000", "name": "Security Review", "agent_id": "claude", "prompt_template": "Review this code for security vulnerabilities:\n\n{trigger_payload}\n\nProvide specific findings with severity levels.", "quality_gate": {"enabled": True, "method": "ai_validation", "validator_agent_id": "claude", "validation_prompt": "Score this security review 0.0-1.0. Does it identify real vulnerabilities? JSON: {\"score\": 0.0, \"feedback\": \"...\"}", "min_score": 0.7, "max_retries": 2, "retry_with_feedback": True}, "routing": {"type": "conditional", "conditions": [{"if": "output_contains:critical", "then": "step_escalate"}], "default": "step_001", "next_step_id": "step_001"}, "order": 0},
                {"step_id": "step_escalate", "name": "Critical Escalation", "agent_id": "claude", "prompt_template": "CRITICAL security issues found. Summarize for immediate human review:\n\n{step_000_output}", "routing": {"type": "human_gate"}, "order": 1},
                {"step_id": "step_001", "name": "Code Quality", "agent_id": "chatgpt", "prompt_template": "Review code quality, style, and best practices:\n\n{trigger_payload}\n\nSecurity context: {step_000_output}", "routing": {"type": "sequential", "next_step_id": "step_002"}, "order": 2},
                {"step_id": "step_002", "name": "Documentation", "agent_id": "chatgpt", "prompt_template": "Update documentation based on code changes and review findings:\n\n{trigger_payload}\n\nReview: {pipeline_context}", "routing": {"type": "sequential"}, "order": 3},
            ],
            "settings": {"max_total_cost_usd": 2.0, "on_failure": "pause_and_notify"},
            "triggers": [{"type": "webhook"}],
        },
        {
            "template_id": "content_pipeline", "name": "Content Production Pipeline",
            "description": "Research → Write → Edit → SEO Optimize. Full content creation workflow.",
            "category": "content",
            "steps": [
                {"step_id": "step_000", "name": "Research", "agent_id": "chatgpt", "prompt_template": "Research the following topic thoroughly. Provide key facts, statistics, and expert opinions:\n\n{trigger_payload}", "routing": {"type": "sequential", "next_step_id": "step_001"}, "order": 0},
                {"step_id": "step_001", "name": "Write Draft", "agent_id": "claude", "prompt_template": "Write a comprehensive article based on this research:\n\n{step_000_output}", "quality_gate": {"enabled": True, "method": "ai_validation", "validator_agent_id": "chatgpt", "validation_prompt": "Score this article 0.0-1.0 on quality, accuracy, engagement. JSON: {\"score\": 0.0, \"feedback\": \"...\"}", "min_score": 0.7, "max_retries": 2}, "routing": {"type": "sequential", "next_step_id": "step_002"}, "order": 1},
                {"step_id": "step_002", "name": "Edit & Polish", "agent_id": "claude", "prompt_template": "Edit this article for clarity, grammar, and flow:\n\n{step_001_output}", "routing": {"type": "sequential", "next_step_id": "step_003"}, "order": 2},
                {"step_id": "step_003", "name": "SEO Optimize", "agent_id": "chatgpt", "prompt_template": "Optimize this article for SEO. Add meta description, optimize headers, suggest keywords:\n\n{step_002_output}", "routing": {"type": "sequential"}, "order": 3},
            ],
            "settings": {"max_total_cost_usd": 3.0, "on_failure": "pause_and_notify"},
            "triggers": [{"type": "manual"}],
        },
        {
            "template_id": "support_triage", "name": "Support Triage Pipeline",
            "description": "Triage → Specialist → QA. Automated customer support handling.",
            "category": "support",
            "steps": [
                {"step_id": "step_000", "name": "Triage", "agent_id": "chatgpt", "prompt_template": "Classify this support request by priority (P1-P4) and category:\n\n{trigger_payload}\n\nRespond with JSON: {\"priority\": \"P2\", \"category\": \"billing\", \"summary\": \"...\"}", "routing": {"type": "sequential", "next_step_id": "step_001"}, "order": 0},
                {"step_id": "step_001", "name": "Draft Response", "agent_id": "claude", "prompt_template": "Draft a helpful response to this support request:\n\nClassification: {step_000_output}\n\nOriginal: {trigger_payload}", "routing": {"type": "sequential", "next_step_id": "step_002"}, "order": 1},
                {"step_id": "step_002", "name": "QA Validation", "agent_id": "chatgpt", "prompt_template": "Validate this support response for accuracy and helpfulness:\n\n{step_001_output}\n\nOriginal request: {trigger_payload}", "quality_gate": {"enabled": True, "method": "ai_validation", "validator_agent_id": "claude", "validation_prompt": "Is this response accurate and helpful? JSON: {\"score\": 0.0, \"feedback\": \"...\"}", "min_score": 0.8, "max_retries": 1}, "routing": {"type": "sequential"}, "order": 2},
            ],
            "settings": {"max_total_cost_usd": 1.0, "on_failure": "skip_step"},
            "triggers": [{"type": "webhook"}],
        },
        {
            "template_id": "data_analysis", "name": "Data Analysis Pipeline",
            "description": "Collect → Analyze → Report. Automated data insights.",
            "category": "analytics",
            "steps": [
                {"step_id": "step_000", "name": "Data Collection", "agent_id": "chatgpt", "prompt_template": "Gather and organize the following data:\n\n{trigger_payload}", "routing": {"type": "sequential", "next_step_id": "step_001"}, "order": 0},
                {"step_id": "step_001", "name": "Analysis", "agent_id": "claude", "prompt_template": "Analyze this data and extract key insights:\n\n{step_000_output}", "routing": {"type": "sequential", "next_step_id": "step_002"}, "order": 1},
                {"step_id": "step_002", "name": "Report", "agent_id": "chatgpt", "prompt_template": "Generate an executive summary report:\n\n{step_001_output}", "routing": {"type": "sequential"}, "order": 2},
            ],
            "settings": {"max_total_cost_usd": 2.0},
            "triggers": [{"type": "schedule", "cron": "0 8 * * 1"}],
        },
        {
            "template_id": "pr_review_bot", "name": "PR Review Bot",
            "description": "Code Review → Summary. Quick automated PR reviews.",
            "category": "development",
            "steps": [
                {"step_id": "step_000", "name": "Code Review", "agent_id": "claude", "prompt_template": "Review this pull request for bugs, security issues, and improvements:\n\n{trigger_payload}", "routing": {"type": "sequential", "next_step_id": "step_001"}, "order": 0},
                {"step_id": "step_001", "name": "Summary", "agent_id": "chatgpt", "prompt_template": "Create a concise PR review summary with approval recommendation:\n\n{step_000_output}", "routing": {"type": "sequential"}, "order": 1},
            ],
            "settings": {"max_total_cost_usd": 1.0},
            "triggers": [{"type": "webhook"}],
        },
        {
            "template_id": "meeting_notes", "name": "Meeting Notes Pipeline",
            "description": "Summarize → Extract Actions → Create Tasks.",
            "category": "productivity",
            "steps": [
                {"step_id": "step_000", "name": "Summarize", "agent_id": "claude", "prompt_template": "Summarize these meeting notes. Extract key decisions and discussion points:\n\n{trigger_payload}", "routing": {"type": "sequential", "next_step_id": "step_001"}, "order": 0},
                {"step_id": "step_001", "name": "Extract Actions", "agent_id": "chatgpt", "prompt_template": "Extract all action items from this meeting summary. Format as a list with owner and deadline:\n\n{step_000_output}", "routing": {"type": "sequential", "next_step_id": "step_002"}, "order": 1},
                {"step_id": "step_002", "name": "Create Tasks", "agent_id": "chatgpt", "prompt_template": "Convert these action items into structured task descriptions:\n\n{step_001_output}", "routing": {"type": "sequential"}, "order": 2},
            ],
            "settings": {"max_total_cost_usd": 1.0},
            "triggers": [{"type": "manual"}],
        },
    ]
