"""Autonomous Deployments — AI agent deployment management with triggers, runs, and governance.

Enables users to create autonomous AI agent deployments that can be triggered
via webhooks, cron schedules, or manually. Each deployment defines an agent team,
objective, allowed tools, and governance policies (cost limits, approval gates).
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



class DeploymentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    agents: list = Field(default_factory=list)
    objective: dict = Field(default_factory=dict)
    allowed_tools: list = Field(default_factory=list)
    policy: dict = Field(default_factory=dict)
    triggers: list = Field(default_factory=list)


def register_deployment_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    # ============ Deployment CRUD ============

    @api_router.get("/workspaces/{ws_id}/deployments")
    async def list_deployments(ws_id: str, request: Request, status: Optional[str] = None):
        user = await _authed_user(request, ws_id)
        query = {"workspace_id": ws_id}
        if status:
            query["status"] = status
        deps = await db.deployments.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        # Attach run stats
        for dep in deps:
            dep["stats"] = await _get_stats(db, dep["deployment_id"])
        return deps

    @api_router.post("/workspaces/{ws_id}/deployments")
    async def create_deployment(ws_id: str, request: Request):
        user = await _authed_user(request, ws_id)
        body = await request.json()
        dep_id = f"dep_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        
        deployment = {
            "deployment_id": dep_id,
            "workspace_id": ws_id,
            "name": body.get("name", "Untitled Deployment"),
            "description": body.get("description", ""),
            "status": "draft",
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "agents": body.get("agents") or [],
            "objective": body.get("objective", {"goal": "", "success_criteria": [], "output_channel_id": ""}),
            "allowed_tools": body.get("allowed_tools") or [],
            "policy": {
                "max_cost_per_run_usd": (body.get("policy") or {}).get("max_cost_per_run_usd", 5.0),
                "max_cost_per_day_usd": (body.get("policy") or {}).get("max_cost_per_day_usd", 50.0),
                "max_actions_per_run": (body.get("policy") or {}).get("max_actions_per_run", 50),
                "max_concurrent_runs": (body.get("policy") or {}).get("max_concurrent_runs", 1),
                "require_human_approval": (body.get("policy") or {}).get("require_human_approval") or [],
                "blocked_tools": (body.get("policy") or {}).get("blocked_tools") or [],
                "auto_pause_on_error_count": (body.get("policy") or {}).get("auto_pause_on_error_count", 3),
                "escalation_channel_id": (body.get("policy") or {}).get("escalation_channel_id", ""),
            },
            "triggers": body.get("triggers", [{"type": "manual"}]),
        }
        await db.deployments.insert_one(deployment)
        deployment.pop("_id", None)
        return deployment

    @api_router.get("/deployments/{dep_id}")
    async def get_deployment(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0})
        if not dep:
            raise HTTPException(404, "Deployment not found")
        dep["stats"] = await _get_stats(db, dep_id)
        return dep

    @api_router.put("/deployments/{dep_id}")
    async def update_deployment(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        body = await request.json()
        dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0})
        if not dep:
            raise HTTPException(404, "Deployment not found")
        
        update = {"updated_at": now_iso()}
        for field in ["name", "description", "agents", "objective", "allowed_tools", "policy", "triggers"]:
            if field in body:
                update[field] = body[field]
        
        await db.deployments.update_one({"deployment_id": dep_id}, {"$set": update})
        dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0})
        if not dep:
            raise HTTPException(404, "Deployment not found")
        dep["stats"] = await _get_stats(db, dep_id)
        return dep

    @api_router.delete("/deployments/{dep_id}")
    async def delete_deployment(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        result = await db.deployments.update_one(
            {"deployment_id": dep_id},
            {"$set": {"status": "archived", "updated_at": now_iso()}}
        )
        if result.modified_count == 0:
            raise HTTPException(404, "Deployment not found")
        return {"message": "Deployment archived"}

    # ============ Deployment Lifecycle ============

    @api_router.post("/deployments/{dep_id}/activate")
    async def activate_deployment(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0})
        if not dep:
            raise HTTPException(404, "Deployment not found")
        if dep["status"] == "active":
            return dep
        # Validate required fields
        if not dep.get("agents"):
            raise HTTPException(400, "At least one agent is required")
        if not (dep.get("objective") or {}).get("goal"):
            raise HTTPException(400, "Objective goal is required")
        
        await db.deployments.update_one(
            {"deployment_id": dep_id},
            {"$set": {"status": "active", "updated_at": now_iso()}}
        )
        dep["status"] = "active"
        dep["stats"] = await _get_stats(db, dep_id)
        return dep

    @api_router.post("/deployments/{dep_id}/pause")
    async def pause_deployment(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        await db.deployments.update_one(
            {"deployment_id": dep_id},
            {"$set": {"status": "paused", "updated_at": now_iso()}}
        )
        # Cancel queued/running runs
        await db.deployment_runs.update_many(
            {"deployment_id": dep_id, "status": {"$in": ["queued", "running"]}},
            {"$set": {"status": "cancelled", "completed_at": now_iso()}}
        )
        dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0})
        if dep:
            dep["stats"] = await _get_stats(db, dep_id)
        return dep or {"message": "Paused"}

    # ============ Trigger a Run ============

    @api_router.post("/deployments/{dep_id}/trigger")
    async def trigger_run(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        
        dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0})
        if not dep:
            raise HTTPException(404, "Deployment not found")
        if dep["status"] != "active":
            raise HTTPException(400, "Deployment must be active to trigger")
        
        # Check concurrent runs
        policy = dep.get("policy") or {}
        max_concurrent = policy.get("max_concurrent_runs", 1)
        active_runs = await db.deployment_runs.count_documents(
            {"deployment_id": dep_id, "status": {"$in": ["queued", "running"]}}
        )
        
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        run_status = "queued" if active_runs >= max_concurrent else "running"
        
        run = {
            "run_id": run_id,
            "deployment_id": dep_id,
            "workspace_id": dep["workspace_id"],
            "status": run_status,
            "trigger_type": body.get("trigger_type", "manual"),
            "trigger_payload": body.get("payload") or {},
            "started_at": now if run_status == "running" else None,
            "completed_at": None,
            "cost_usd": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "actions_taken": 0,
            "error": None,
            "output_summary": None,
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.deployment_runs.insert_one(run)
        run.pop("_id", None)
        
        if run_status == "running":
            asyncio.create_task(_execute_run(db, dep, run))
        
        return {"run_id": run_id, "status": run_status}

    # ============ Run Management ============

    @api_router.get("/deployments/{dep_id}/runs")
    async def list_runs(dep_id: str, request: Request, limit: int = 20):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        runs = await db.deployment_runs.find(
            {"deployment_id": dep_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return runs

    @api_router.get("/deployment-runs/{run_id}")
    async def get_run(run_id: str, request: Request):
        user = await get_current_user(request)
        run = await db.deployment_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @api_router.get("/deployment-runs/{run_id}/actions")
    async def get_run_actions(run_id: str, request: Request):
        user = await get_current_user(request)
        actions = await db.deployment_action_log.find(
            {"run_id": run_id}, {"_id": 0}
        ).sort("sequence", 1).to_list(200)
        return actions

    @api_router.post("/deployment-runs/{run_id}/approve")
    async def approve_run(run_id: str, request: Request):
        user = await get_current_user(request)
        run = await db.deployment_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        if run.get("status") != "paused_approval":
            raise HTTPException(400, "Run is not paused for approval")
        
        await db.deployment_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "running", "error": None}}
        )
        # Resume execution
        dep = await db.deployments.find_one({"deployment_id": run["deployment_id"]}, {"_id": 0})
        if dep:
            asyncio.create_task(_execute_run(db, dep, {**run, "status": "running"}))
        return {"message": "Approved, run resumed"}

    @api_router.post("/deployment-runs/{run_id}/reject")
    async def reject_run(run_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        reason = body.get("reason", "Rejected by user")
        
        await db.deployment_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed", "error": f"Rejected: {reason}", "completed_at": now_iso()}}
        )
        return {"message": "Rejected, run failed"}

    @api_router.post("/deployment-runs/{run_id}/cancel")
    async def cancel_run(run_id: str, request: Request):
        user = await get_current_user(request)
        run = await db.deployment_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        if run.get("status") in ["completed", "failed", "cancelled"]:
            return {"message": "Run already in terminal state"}
        
        await db.deployment_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "cancelled", "completed_at": now_iso(), "error": "Cancelled by user"}}
        )
        return {"message": "Run cancelled"}

    # ============ Webhook Trigger Endpoint ============

    @api_router.post("/webhooks/deployments/{webhook_token}")
    async def webhook_trigger(webhook_token: str, request: Request):
        """Inbound webhook to trigger a deployment run."""
        wh = await db.deployment_webhooks.find_one({"token": webhook_token, "active": True}, {"_id": 0})
        if not wh:
            raise HTTPException(404, "Webhook not found or inactive")
        dep_id = wh["deployment_id"]
        dep = await db.deployments.find_one({"deployment_id": dep_id, "status": "active"}, {"_id": 0})
        if not dep:
            raise HTTPException(400, "Deployment not active")
        
        body = {}
        try:
            body = await request.json()
        except Exception as e:
            logger.warning(f"Non-critical error at line 325: {e}")
        
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        run = {
            "run_id": run_id, "deployment_id": dep_id, "workspace_id": dep["workspace_id"],
            "status": "running", "trigger_type": "webhook", "trigger_payload": body,
            "started_at": now, "completed_at": None, "cost_usd": 0.0,
            "tokens_in": 0, "tokens_out": 0, "actions_taken": 0,
            "error": None, "output_summary": None, "created_by": "webhook", "created_at": now,
        }
        await db.deployment_runs.insert_one(run)
        run.pop("_id", None)
        asyncio.create_task(_execute_run(db, dep, run))
        return {"run_id": run_id, "status": "running"}

    # ============ Webhook Management ============

    @api_router.post("/deployments/{dep_id}/webhooks")
    async def create_webhook(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        body = await request.json()
        import secrets
        token = secrets.token_urlsafe(32)
        wh = {
            "webhook_id": f"wh_{uuid.uuid4().hex[:12]}",
            "deployment_id": dep_id,
            "token": token,
            "events": body.get("events", ["*"]),
            "active": True,
            "created_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.deployment_webhooks.insert_one(wh)
        wh.pop("_id", None)
        base_url = str(request.base_url).rstrip("/")
        wh["url"] = f"{base_url}/api/webhooks/deployments/{token}"
        return wh

    @api_router.get("/deployments/{dep_id}/webhooks")
    async def list_webhooks(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        whs = await db.deployment_webhooks.find({"deployment_id": dep_id}, {"_id": 0}).to_list(20)
        base_url = str(request.base_url).rstrip("/")
        for wh in whs:
            wh["url"] = f"{base_url}/api/webhooks/deployments/{wh['token']}"
        return whs

    @api_router.delete("/deployment-webhooks/{wh_id}")
    async def delete_webhook(wh_id: str, request: Request):
        user = await get_current_user(request)
        await db.deployment_webhooks.update_one({"webhook_id": wh_id}, {"$set": {"active": False}})
        return {"message": "Webhook deactivated"}

    # ============ Cron Schedule Management ============

    @api_router.post("/deployments/{dep_id}/schedules")
    async def create_schedule(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        body = await request.json()
        cron_expr = body.get("schedule", "")
        if not cron_expr:
            raise HTTPException(400, "Cron schedule expression required")
        
        sched = {
            "schedule_id": f"dsched_{uuid.uuid4().hex[:12]}",
            "deployment_id": dep_id,
            "schedule": cron_expr,
            "description": body.get("description", ""),
            "enabled": True,
            "last_run_at": None,
            "next_run_at": None,
            "created_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.deployment_schedules.insert_one(sched)
        sched.pop("_id", None)
        return sched

    @api_router.get("/deployments/{dep_id}/schedules")
    async def list_schedules(dep_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_deployment_access
        await require_deployment_access(db, user, dep_id)
        scheds = await db.deployment_schedules.find({"deployment_id": dep_id, "enabled": True}, {"_id": 0}).to_list(20)
        return scheds

    @api_router.delete("/deployment-schedules/{sched_id}")
    async def delete_schedule(sched_id: str, request: Request):
        user = await get_current_user(request)
        await db.deployment_schedules.update_one({"schedule_id": sched_id}, {"$set": {"enabled": False}})
        return {"message": "Schedule disabled"}

    # ============ Deployment Templates ============

    @api_router.get("/deployment-templates")
    async def list_templates(request: Request):
        user = await get_current_user(request)
        return DEPLOYMENT_TEMPLATES

    @api_router.post("/workspaces/{ws_id}/deployments/from-template")
    async def create_from_template(ws_id: str, request: Request):
        user = await _authed_user(request, ws_id)
        body = await request.json()
        template_id = body.get("template_id", "")
        template = next((t for t in DEPLOYMENT_TEMPLATES if t["id"] == template_id), None)
        if not template:
            raise HTTPException(404, "Template not found")
        
        dep_id = f"dep_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        deployment = {
            "deployment_id": dep_id,
            "workspace_id": ws_id,
            "name": body.get("name", template["name"]),
            "description": template["description"],
            "status": "draft",
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "agents": template["agents"],
            "objective": {**template["objective"], "output_channel_id": body.get("output_channel_id", "")},
            "allowed_tools": template["allowed_tools"],
            "policy": template["policy"],
            "triggers": template["triggers"],
        }
        await db.deployments.insert_one(deployment)
        deployment.pop("_id", None)
        return deployment

    # ============ Plan Limits ============

    @api_router.get("/workspaces/{ws_id}/deployment-limits")
    async def get_deployment_limits(ws_id: str, request: Request):
        user = await _authed_user(request, ws_id)
        plan = user.get("plan", "free")
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        active_count = await db.deployments.count_documents({"workspace_id": ws_id, "status": {"$in": ["active", "draft", "paused"]}})
        from nexus_utils import safe_regex
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        runs_today = await db.deployment_runs.count_documents({
            "workspace_id": ws_id, "created_at": {"$regex": f"^{safe_regex(today)}"}
        })
        return {
            "plan": plan,
            "max_deployments": limits["deployments"],
            "max_runs_per_day": limits["runs_per_day"],
            "current_deployments": active_count,
            "runs_today": runs_today,
            "can_create": limits["deployments"] == -1 or active_count < limits["deployments"],
            "can_run": limits["runs_per_day"] == -1 or runs_today < limits["runs_per_day"],
        }


# ============ Multi-Step Execution Engine ============

async def _execute_run(db, deployment, run):
    """Execute a deployment run with multi-step agent loop (think → act → evaluate → repeat)."""
    from ai_providers import call_ai_direct
    from collaboration_core import get_ai_key_for_agent
    from deployment_governance import check_policy, check_auto_pause
    
    dep_id = deployment["deployment_id"]
    run_id = run["run_id"]
    ws_id = deployment["workspace_id"]
    policy = deployment.get("policy") or {}
    max_steps = min(policy.get("max_actions_per_run", 20), 50)
    
    try:
        agents = deployment.get("agents") or []
        if not agents:
            raise ValueError("No agents configured")
        
        primary_agent = agents[0]
        agent_key = primary_agent.get("agent_key", "chatgpt")
        
        user_id = run.get("created_by", deployment.get("created_by", ""))
        api_key, key_source = await get_ai_key_for_agent(user_id, ws_id, agent_key)
        if not api_key:
            raise ValueError(f"No API key available for agent {agent_key}")
        
        objective = deployment.get("objective") or {}
        goal = objective.get("goal", "")
        criteria = objective.get("success_criteria") or []
        
        from nexus_config import AI_MODELS
        model_config = AI_MODELS.get(agent_key, {})
        model = primary_agent.get("model_override") or model_config.get("model", "")
        
        system_prompt = primary_agent.get("system_prompt_override", "") or f"""You are an autonomous AI agent executing a deployment task.

OBJECTIVE: {goal}
SUCCESS CRITERIA: {', '.join(criteria) if criteria else 'Complete the objective fully'}

You operate in a LOOP. Each response should either:
1. COMPLETE the task and say "TASK_COMPLETE:" followed by a summary
2. REQUEST a tool call by saying "TOOL_REQUEST: tool_name | arguments_json"
3. CONTINUE working and provide your progress

RULES:
- Work step by step toward the objective
- When done, ALWAYS start your final message with "TASK_COMPLETE:"
- Be concise and efficient
- Report what you accomplished"""
        
        # Build initial context
        trigger_info = run.get("trigger_payload") or {}
        conversation = [f"Execute the deployment objective."]
        if trigger_info:
            conversation.append(f"Trigger context: {str(trigger_info)[:500]}")
        
        total_cost = 0.0
        total_tokens_in = 0
        total_tokens_out = 0
        step = 0
        
        import time
        
        # Multi-step execution loop
        while step < max_steps:
            step += 1
            
            # Check if run was cancelled
            current_run = await db.deployment_runs.find_one({"run_id": run_id}, {"_id": 0, "status": 1})
            if current_run and current_run.get("status") in ["cancelled", "failed"]:
                break
            
            user_prompt = "\n".join(conversation[-5:])  # Last 5 messages for context
            
            # Policy check
            policy_result = await check_policy(db, deployment, {**run, "actions_taken": step - 1, "cost_usd": total_cost}, "ai_inference", 0)
            if policy_result["action"] == "block":
                await _log_action(db, run_id, dep_id, step, "policy_block", agent_key, None, user_prompt[:300], policy_result["reason"], 0, 0, 0, 0, "blocked")
                raise ValueError(f"Policy blocked: {policy_result['reason']}")
            
            start = time.time()
            response = await call_ai_direct(agent_key, api_key, system_prompt, user_prompt, model_override=model, workspace_id=ws_id, db=db)
            duration_ms = int((time.time() - start) * 1000)
            
            input_tokens = max(1, len(system_prompt + user_prompt) // 4)
            output_tokens = max(1, len(response) // 4)
            est_cost = round((input_tokens * 10 + output_tokens * 30) / 1_000_000, 4)
            total_cost += est_cost
            total_tokens_in += input_tokens
            total_tokens_out += output_tokens
            
            await _log_action(db, run_id, dep_id, step, "ai_inference", agent_key, None, user_prompt[:300], response[:2000], est_cost, input_tokens, output_tokens, duration_ms, "passed")
            
            # Update run stats
            await db.deployment_runs.update_one({"run_id": run_id}, {"$set": {
                "cost_usd": total_cost, "tokens_in": total_tokens_in, "tokens_out": total_tokens_out, "actions_taken": step
            }})
            
            # Check for completion
            if "TASK_COMPLETE:" in response:
                summary = response.split("TASK_COMPLETE:", 1)[1].strip()[:500]
                await db.deployment_runs.update_one({"run_id": run_id}, {"$set": {
                    "status": "completed", "completed_at": now_iso(), "output_summary": summary,
                    "cost_usd": total_cost, "tokens_in": total_tokens_in, "tokens_out": total_tokens_out, "actions_taken": step
                }})
                # Post to output channel
                output_ch = objective.get("output_channel_id")
                if output_ch:
                    await db.messages.insert_one({
                        "message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": output_ch,
                        "sender_type": "system", "sender_id": "deployment",
                        "sender_name": f"Deployment: {deployment.get('name', '')}",
                        "content": f"**Deployment Run Complete** ({step} steps, ${total_cost:.4f})\n\n{summary}",
                        "created_at": now_iso(),
                    })
                logger.info(f"Deployment run {run_id} completed in {step} steps (${total_cost:.4f})")
                return
            
            # Add response to conversation for next iteration
            conversation.append(f"Agent response: {response[:500]}")
            conversation.append("Continue working on the objective. If done, say TASK_COMPLETE: followed by summary.")
        
        # Max steps reached
        await db.deployment_runs.update_one({"run_id": run_id}, {"$set": {
            "status": "completed", "completed_at": now_iso(),
            "output_summary": f"Completed after {step} steps (max reached). Last: {response[:200] if response else 'N/A'}",
            "cost_usd": total_cost, "tokens_in": total_tokens_in, "tokens_out": total_tokens_out, "actions_taken": step
        }})
        logger.info(f"Deployment run {run_id} completed (max steps {step})")
        
    except Exception as e:
        logger.error(f"Deployment run {run_id} failed: {e}")
        await db.deployment_runs.update_one({"run_id": run_id}, {"$set": {
            "status": "failed", "error": str(e)[:500], "completed_at": now_iso(),
        }})
        await check_auto_pause(db, dep_id)


async def _log_action(db, run_id, dep_id, seq, action_type, agent_key, tool_name, inp, out, cost, tok_in, tok_out, dur, policy):
    """Log a deployment action."""
    action = {
        "action_id": f"act_{uuid.uuid4().hex[:12]}", "run_id": run_id, "deployment_id": dep_id,
        "sequence": seq, "action_type": action_type, "agent_key": agent_key,
        "tool_name": tool_name, "input": inp, "output": out,
        "cost_usd": cost, "tokens_in": tok_in, "tokens_out": tok_out,
        "duration_ms": dur, "policy_check": policy, "created_at": now_iso(),
    }
    await db.deployment_action_log.insert_one(action)


async def _get_stats(db, deployment_id):
    """Aggregate run stats for a deployment."""
    runs = await db.deployment_runs.find(
        {"deployment_id": deployment_id}, {"_id": 0, "status": 1, "cost_usd": 1, "started_at": 1}
    ).to_list(500)
    
    total = len(runs)
    completed = sum(1 for r in runs if r.get("status") == "completed")
    failed = sum(1 for r in runs if r.get("status") == "failed")
    cost = sum(r.get("cost_usd", 0) for r in runs)
    last_run = runs[0] if runs else None
    
    return {
        "total_runs": total,
        "successful_runs": completed,
        "failed_runs": failed,
        "total_cost_usd": round(cost, 2),
        "last_run_at": last_run.get("started_at") if last_run else None,
    }


# ============ Plan Limits ============

PLAN_LIMITS = {
    "free": {"deployments": 0, "runs_per_day": 0},
    "starter": {"deployments": 2, "runs_per_day": 10},
    "pro": {"deployments": 10, "runs_per_day": 100},
    "team": {"deployments": 25, "runs_per_day": 500},
    "enterprise": {"deployments": -1, "runs_per_day": -1},
}

# ============ Deployment Templates ============

DEPLOYMENT_TEMPLATES = [
    {
        "id": "code_reviewer",
        "name": "Code Review Bot",
        "description": "Automatically reviews code changes and provides feedback on quality, security, and best practices.",
        "agents": [{"agent_key": "chatgpt", "role": "primary"}],
        "objective": {"goal": "Review the provided code changes for bugs, security issues, and best practices. Provide actionable feedback.", "success_criteria": ["All code reviewed", "Security issues flagged", "Improvement suggestions provided"]},
        "allowed_tools": ["repo_read_file", "repo_list_files", "create_task"],
        "policy": {"max_cost_per_run_usd": 2.0, "max_cost_per_day_usd": 20.0, "max_actions_per_run": 10, "max_concurrent_runs": 1, "require_human_approval": [], "blocked_tools": ["repo_write_file"], "auto_pause_on_error_count": 3, "escalation_channel_id": ""},
        "triggers": [{"type": "webhook", "events": ["pull_request.opened"]}, {"type": "manual"}],
    },
    {
        "id": "daily_standup",
        "name": "Daily Standup Reporter",
        "description": "Generates a daily standup report summarizing project progress, blockers, and next steps.",
        "agents": [{"agent_key": "chatgpt", "role": "primary"}],
        "objective": {"goal": "Generate a daily standup report covering: what was accomplished yesterday, what's planned today, and any blockers.", "success_criteria": ["Report covers all active projects", "Blockers identified"]},
        "allowed_tools": ["repo_list_files", "list_tasks"],
        "policy": {"max_cost_per_run_usd": 1.0, "max_cost_per_day_usd": 5.0, "max_actions_per_run": 5, "max_concurrent_runs": 1, "require_human_approval": [], "blocked_tools": ["repo_write_file", "execute_code"], "auto_pause_on_error_count": 3, "escalation_channel_id": ""},
        "triggers": [{"type": "cron", "schedule": "0 9 * * 1-5"}, {"type": "manual"}],
    },
    {
        "id": "security_scanner",
        "name": "Security Scanner",
        "description": "Scans repository code for security vulnerabilities, hardcoded secrets, and dependency issues.",
        "agents": [{"agent_key": "claude", "role": "primary"}],
        "objective": {"goal": "Scan all code files for security vulnerabilities including: hardcoded secrets, SQL injection, XSS, insecure dependencies, and authentication bypasses.", "success_criteria": ["All files scanned", "Vulnerabilities classified by severity", "Remediation steps provided"]},
        "allowed_tools": ["repo_read_file", "repo_list_files", "create_task"],
        "policy": {"max_cost_per_run_usd": 5.0, "max_cost_per_day_usd": 30.0, "max_actions_per_run": 20, "max_concurrent_runs": 1, "require_human_approval": [], "blocked_tools": ["repo_write_file", "execute_code"], "auto_pause_on_error_count": 2, "escalation_channel_id": ""},
        "triggers": [{"type": "cron", "schedule": "0 2 * * 1"}, {"type": "manual"}],
    },
    {
        "id": "doc_generator",
        "name": "Documentation Generator",
        "description": "Automatically generates or updates documentation based on code changes.",
        "agents": [{"agent_key": "gemini", "role": "primary"}],
        "objective": {"goal": "Analyze the codebase and generate comprehensive documentation including: API docs, README updates, and architecture overview.", "success_criteria": ["All public APIs documented", "README up to date"]},
        "allowed_tools": ["repo_read_file", "repo_list_files", "repo_write_file"],
        "policy": {"max_cost_per_run_usd": 3.0, "max_cost_per_day_usd": 15.0, "max_actions_per_run": 15, "max_concurrent_runs": 1, "require_human_approval": ["repo_write_file"], "blocked_tools": ["execute_code"], "auto_pause_on_error_count": 3, "escalation_channel_id": ""},
        "triggers": [{"type": "manual"}],
    },
    {
        "id": "test_generator",
        "name": "Test Suite Generator",
        "description": "Generates unit and integration tests for existing code.",
        "agents": [{"agent_key": "deepseek", "role": "primary"}],
        "objective": {"goal": "Analyze the codebase and generate comprehensive test suites for untested code paths. Focus on edge cases and error handling.", "success_criteria": ["Tests generated for all major functions", "Edge cases covered"]},
        "allowed_tools": ["repo_read_file", "repo_list_files", "repo_write_file"],
        "policy": {"max_cost_per_run_usd": 4.0, "max_cost_per_day_usd": 20.0, "max_actions_per_run": 20, "max_concurrent_runs": 1, "require_human_approval": ["repo_write_file"], "blocked_tools": ["execute_code"], "auto_pause_on_error_count": 3, "escalation_channel_id": ""},
        "triggers": [{"type": "manual"}],
    },
]
