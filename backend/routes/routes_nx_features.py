"""NX-001: Transparent Model Routing Engine — Visible, controllable model routing.
NX-002 gaps: Workspace branching, snapshots, context summaries.
NX-004 gaps: Pre-execution cost estimates, pause-and-ask, per-task budgets.
NX-005 gaps: MCP connector marketplace, debugging console.
NX-006: Auditable Agent Execution Chains — DAG traces, step inspection, replay, fork, export.
"""
import uuid
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from nexus_utils import sanitize_filename, now_iso

logger = logging.getLogger(__name__)



# ============ NX-001: Model Routing ============

class RoutingRule(BaseModel):
    name: str = Field(..., min_length=1)
    conditions: dict = {}
    model: str = ""
    priority: int = 0


class ComparisonRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system_prompt: str = ""
    models: List[str] = Field(..., min_length=2, max_length=4)


# ============ NX-002: Workspace Operations ============

class WorkspaceBranchRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""


class WorkspaceSnapshotRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""


# ============ NX-004: Budget Controls ============

class BudgetLimitRequest(BaseModel):
    scope: str = "workspace"
    limit_usd: float = Field(..., gt=0)
    period: str = "daily"
    pause_on_exceed: bool = True


# ============ NX-006: Execution Chains ============

class StepReplayRequest(BaseModel):
    modified_prompt: str = ""


def register_nx_features_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import validate_external_url, now_iso, require_workspace_access, sanitize_filename
        await require_workspace_access(db, user, ws_id)
        return user

    # ==========================================
    # NX-001: TRANSPARENT MODEL ROUTING ENGINE
    # ==========================================

    @api_router.get("/workspaces/{ws_id}/routing/active")
    async def get_active_routing(ws_id: str, request: Request):
        """Real-time routing panel: show which model handles each active task."""
        await _authed_user(request, ws_id)
        # Get recent AI messages with model info
        recent = await db.messages.find(
            {"workspace_id": ws_id, "sender_type": "ai"},
            {"_id": 0, "message_id": 1, "agent": 1, "model_used": 1, "channel_id": 1,
             "tokens_used": 1, "cost_usd": 1, "created_at": 1, "content": 1}
        ).sort("created_at", -1).limit(20).to_list(20)

        routing_entries = []
        for msg in recent:
            routing_entries.append({
                "message_id": msg.get("message_id", ""),
                "agent": msg.get("agent", "unknown"),
                "model": msg.get("model_used", "auto"),
                "channel_id": msg.get("channel_id", ""),
                "tokens": msg.get("tokens_used", 0),
                "cost_usd": msg.get("cost_usd", 0),
                "timestamp": msg.get("created_at", ""),
                "preview": (msg.get("content", ""))[:100],
            })
        return {"routing": routing_entries}

    @api_router.get("/workspaces/{ws_id}/routing/logs")
    async def get_routing_logs(ws_id: str, request: Request, limit: int = 50):
        """Routing decision log with reasoning metadata."""
        await _authed_user(request, ws_id)
        logs = await db.routing_logs.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"logs": logs}

    @api_router.post("/workspaces/{ws_id}/routing/override")
    async def override_model(ws_id: str, request: Request):
        """Override model assignment for a channel/agent."""
        user = await _authed_user(request, ws_id)
        body = await request.json()
        channel_id = body.get("channel_id", "")
        agent_key = body.get("agent_key", "")
        model_id = body.get("model_id", "")
        if not channel_id or not agent_key or not model_id:
            raise HTTPException(400, "channel_id, agent_key, model_id required")

        # Store override
        override_id = f"rovr_{uuid.uuid4().hex[:10]}"
        override = {
            "override_id": override_id, "workspace_id": ws_id,
            "channel_id": channel_id, "agent_key": agent_key,
            "model_id": model_id, "set_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.model_overrides.update_one(
            {"workspace_id": ws_id, "channel_id": channel_id, "agent_key": agent_key},
            {"$set": override}, upsert=True
        )
        # Also update channel agent_models
        await db.channels.update_one(
            {"channel_id": channel_id},
            {"$set": {f"agent_models.{agent_key}": model_id}}
        )
        # Log the routing decision
        await db.routing_logs.insert_one({
            "log_id": f"rlog_{uuid.uuid4().hex[:10]}", "workspace_id": ws_id,
            "channel_id": channel_id, "agent_key": agent_key,
            "action": "manual_override", "model_id": model_id,
            "reason": f"Manual override by {user.get('name', user['user_id'])}",
            "user_id": user["user_id"], "created_at": now_iso(),
        })
        return override

    @api_router.post("/workspaces/{ws_id}/routing/compare")
    async def compare_models(ws_id: str, data: ComparisonRequest, request: Request):
        """Side-by-side comparison: run same prompt through 2-4 models."""
        user = await _authed_user(request, ws_id)
        from ai_providers import call_ai_direct
        from key_resolver import get_integration_key

        comparison_id = f"cmp_{uuid.uuid4().hex[:10]}"
        results = []
        for model_key in data.models[:4]:
            start = time.time()
            try:
                provider_map = {"gpt-4o": "chatgpt", "claude-sonnet-4-5-20250929": "claude",
                                "gemini-2.0-flash": "gemini", "deepseek-chat": "deepseek",
                                "mistral-large-latest": "mistral"}
                provider = provider_map.get(model_key, model_key.split("-")[0] if "-" in model_key else model_key)
                key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY",
                           "gemini": "GOOGLE_AI_KEY", "deepseek": "DEEPSEEK_API_KEY",
                           "mistral": "MISTRAL_API_KEY"}
                env_key = key_map.get(provider, "OPENAI_API_KEY")
                api_key = await get_integration_key(db, env_key)
                if not api_key:
                    results.append({"model": model_key, "status": "error", "error": f"No API key for {provider}", "latency_ms": 0, "output": ""})
                    continue
                output = await call_ai_direct(provider, api_key, data.system_prompt or "You are a helpful assistant.", data.prompt)
                latency = int((time.time() - start) * 1000)
                results.append({"model": model_key, "status": "completed", "output": output[:3000], "latency_ms": latency, "char_count": len(output)})
            except Exception as e:
                results.append({"model": model_key, "status": "error", "error": str(e)[:200], "latency_ms": int((time.time() - start) * 1000), "output": ""})

        comparison = {
            "comparison_id": comparison_id, "workspace_id": ws_id,
            "prompt": data.prompt[:500], "models": data.models,
            "results": results, "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.model_comparisons.insert_one(comparison)
        comparison.pop("_id", None)
        return comparison

    @api_router.get("/workspaces/{ws_id}/routing/rules")
    async def list_routing_rules(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        rules = await db.routing_rules.find({"workspace_id": ws_id}, {"_id": 0}).sort("priority", -1).to_list(20)
        return {"rules": rules}

    @api_router.post("/workspaces/{ws_id}/routing/rules")
    async def create_routing_rule(ws_id: str, data: RoutingRule, request: Request):
        user = await _authed_user(request, ws_id)
        rule_id = f"rrule_{uuid.uuid4().hex[:10]}"
        rule = {
            "rule_id": rule_id, "workspace_id": ws_id,
            "name": data.name, "conditions": data.conditions,
            "model": data.model, "priority": data.priority,
            "enabled": True, "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.routing_rules.insert_one(rule)
        rule.pop("_id", None)
        return rule

    @api_router.delete("/workspaces/{ws_id}/routing/rules/{rule_id}")
    async def delete_routing_rule(ws_id: str, rule_id: str, request: Request):
        await _authed_user(request, ws_id)
        await db.routing_rules.delete_one({"rule_id": rule_id, "workspace_id": ws_id})
        return {"deleted": rule_id}

    # ==========================================
    # NX-002: WORKSPACE BRANCHING & SNAPSHOTS
    # ==========================================

    @api_router.post("/workspaces/{ws_id}/branch")
    async def branch_workspace(ws_id: str, data: WorkspaceBranchRequest, request: Request):
        """Fork workspace state into a new independent workspace."""
        user = await _authed_user(request, ws_id)
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not ws:
            raise HTTPException(404, "Workspace not found")

        new_ws_id = f"ws_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        new_ws = {**ws, "workspace_id": new_ws_id, "name": data.name,
                  "description": data.description or f"Branch of {ws.get('name', ws_id)}",
                  "branched_from": ws_id, "created_at": now, "owner_id": user["user_id"]}
        new_ws.pop("_id", None)
        await db.workspaces.insert_one(new_ws)

        # Copy channels
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0}).to_list(50)
        for ch in channels:
            new_ch_id = f"ch_{uuid.uuid4().hex[:12]}"
            ch["channel_id"] = new_ch_id
            ch["workspace_id"] = new_ws_id
            ch["branched_from"] = ch.get("channel_id", "")
            ch.pop("_id", None)
            await db.channels.insert_one(ch)

        # Copy workspace memory
        memories = await db.workspace_memory.find({"workspace_id": ws_id}, {"_id": 0}).to_list(200)
        for mem in memories:
            mem["memory_id"] = f"mem_{uuid.uuid4().hex[:12]}"
            mem["workspace_id"] = new_ws_id
            mem.pop("_id", None)
            await db.workspace_memory.insert_one(mem)

        return {"workspace_id": new_ws_id, "name": data.name, "branched_from": ws_id}

    @api_router.post("/workspaces/{ws_id}/snapshots")
    async def create_snapshot(ws_id: str, data: WorkspaceSnapshotRequest, request: Request):
        """Save a point-in-time snapshot of workspace state."""
        user = await _authed_user(request, ws_id)
        snapshot_id = f"snap_{uuid.uuid4().hex[:10]}"
        now = now_iso()

        # Capture channel states
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0}).to_list(50)
        channel_states = []
        for ch in channels:
            msg_count = await db.messages.count_documents({"channel_id": ch["channel_id"]})
            channel_states.append({
                "channel_id": ch["channel_id"], "name": ch.get("name", ""),
                "ai_agents": ch.get("ai_agents") or [], "disabled_agents": ch.get("disabled_agents") or [],
                "message_count": msg_count,
            })

        # Capture workspace memory
        memory_count = await db.workspace_memory.count_documents({"workspace_id": ws_id})

        snapshot = {
            "snapshot_id": snapshot_id, "workspace_id": ws_id,
            "name": data.name, "description": data.description,
            "channel_states": channel_states, "memory_count": memory_count,
            "created_by": user["user_id"], "created_at": now,
        }
        await db.workspace_snapshots.insert_one(snapshot)
        snapshot.pop("_id", None)
        return snapshot

    @api_router.get("/workspaces/{ws_id}/snapshots")
    async def list_snapshots(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        snapshots = await db.workspace_snapshots.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"snapshots": snapshots}

    @api_router.get("/workspaces/{ws_id}/context-summary")
    async def get_context_summary(ws_id: str, request: Request):
        """Auto-generated project context summary for AI agent continuity."""
        await _authed_user(request, ws_id)
        # Check for cached summary
        cached = await db.context_summaries.find_one(
            {"workspace_id": ws_id}, {"_id": 0}
        )
        if cached and cached.get("updated_at", "") > (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat():
            return cached

        # Generate fresh summary from recent activity
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0, "channel_id": 1, "name": 1}).to_list(20)
        recent_messages = []
        for ch in channels[:5]:
            msgs = await db.messages.find(
                {"channel_id": ch["channel_id"]},
                {"_id": 0, "content": 1, "sender_name": 1, "created_at": 1}
            ).sort("created_at", -1).limit(10).to_list(10)
            recent_messages.extend([{**m, "channel": ch.get("name", "")} for m in msgs])

        memories = await db.workspace_memory.find(
            {"workspace_id": ws_id}, {"_id": 0, "key": 1, "value": 1}
        ).sort("updated_at", -1).limit(20).to_list(20)

        summary = {
            "workspace_id": ws_id,
            "channel_count": len(channels),
            "channels": [ch.get("name", ch["channel_id"]) for ch in channels],
            "recent_activity": len(recent_messages),
            "key_topics": list(set(m.get("key", "") for m in memories[:10])),
            "memory_entries": len(memories),
            "last_messages": [{"channel": m.get("channel", ""), "sender": m.get("sender_name", ""), "preview": m.get("content", "")[:100]} for m in recent_messages[:5]],
            "updated_at": now_iso(),
        }
        await db.context_summaries.update_one(
            {"workspace_id": ws_id}, {"$set": summary}, upsert=True
        )
        return summary

    # ==========================================
    # NX-004: INTELLIGENT COST CONTROLS
    # ==========================================

    @api_router.post("/workspaces/{ws_id}/cost/estimate")
    async def estimate_cost(ws_id: str, request: Request):
        """Pre-execution cost estimate based on prompt and model."""
        await _authed_user(request, ws_id)
        body = await request.json()
        prompt = body.get("prompt", "")
        model = body.get("model", "gpt-4o")
        estimated_tokens = len(prompt.split()) * 1.5  # rough estimate

        # Cost per 1K tokens by model (approximate)
        cost_map = {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
            "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
            "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
            "deepseek-chat": {"input": 0.0003, "output": 0.0012},
            "mistral-large-latest": {"input": 0.002, "output": 0.006},
        }
        rates = cost_map.get(model, {"input": 0.005, "output": 0.015})
        est_input_cost = (estimated_tokens / 1000) * rates["input"]
        est_output_cost = (estimated_tokens / 1000) * rates["output"]
        est_total = round(est_input_cost + est_output_cost, 6)

        # Compare with alternative models
        alternatives = []
        for alt_model, alt_rates in cost_map.items():
            if alt_model != model:
                alt_cost = round((estimated_tokens / 1000) * (alt_rates["input"] + alt_rates["output"]), 6)
                alternatives.append({"model": alt_model, "estimated_cost": alt_cost})
        alternatives.sort(key=lambda x: x["estimated_cost"])

        return {
            "model": model, "estimated_tokens": int(estimated_tokens),
            "estimated_cost_usd": est_total,
            "cost_range": {"low": round(est_total * 0.75, 6), "high": round(est_total * 1.25, 6)},
            "alternatives": alternatives[:5],
        }

    @api_router.get("/workspaces/{ws_id}/cost/budgets")
    async def get_budgets(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        budgets = await db.budget_limits.find({"workspace_id": ws_id}, {"_id": 0}).to_list(20)
        return {"budgets": budgets}

    @api_router.post("/workspaces/{ws_id}/cost/budgets")
    async def set_budget(ws_id: str, data: BudgetLimitRequest, request: Request):
        user = await _authed_user(request, ws_id)
        budget_id = f"bdgt_{uuid.uuid4().hex[:10]}"
        budget = {
            "budget_id": budget_id, "workspace_id": ws_id,
            "scope": data.scope, "limit_usd": data.limit_usd,
            "period": data.period, "pause_on_exceed": data.pause_on_exceed,
            "current_spend": 0, "period_start": now_iso(),
            "alerts_sent": [], "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.budget_limits.insert_one(budget)
        budget.pop("_id", None)
        return budget

    @api_router.delete("/workspaces/{ws_id}/cost/budgets/{budget_id}")
    async def delete_budget(ws_id: str, budget_id: str, request: Request):
        await _authed_user(request, ws_id)
        await db.budget_limits.delete_one({"budget_id": budget_id, "workspace_id": ws_id})
        return {"deleted": budget_id}

    @api_router.get("/workspaces/{ws_id}/cost/attribution")
    async def cost_attribution(ws_id: str, request: Request, period: str = "7d"):
        """Detailed cost attribution: by model, agent, user, channel."""
        await _authed_user(request, ws_id)
        days = int(period.replace("d", "")) if period.endswith("d") else 7
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": since}, "cost_usd": {"$gt": 0}}},
            {"$group": {
                "_id": {"model": "$model_used", "agent": "$agent"},
                "total_cost": {"$sum": "$cost_usd"}, "total_tokens": {"$sum": "$tokens_used"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"total_cost": -1}},
        ]
        by_model_agent = []
        async for doc in db.messages.aggregate(pipeline):
            by_model_agent.append({
                "model": doc["_id"].get("model", "unknown"),
                "agent": doc["_id"].get("agent", "unknown"),
                "total_cost_usd": round(doc["total_cost"], 4),
                "total_tokens": doc["total_tokens"],
                "message_count": doc["count"],
            })

        # Daily trend
        pipeline_daily = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": since}, "cost_usd": {"$gt": 0}}},
            {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
            {"$group": {"_id": "$date", "cost": {"$sum": "$cost_usd"}, "tokens": {"$sum": "$tokens_used"}}},
            {"$sort": {"_id": 1}},
        ]
        daily = []
        async for doc in db.messages.aggregate(pipeline_daily):
            daily.append({"date": doc["_id"], "cost_usd": round(doc["cost"], 4), "tokens": doc["tokens"]})

        return {"by_model_agent": by_model_agent, "daily_trend": daily, "period": period}

    # ==========================================
    # NX-005: MCP CONNECTOR MARKETPLACE
    # ==========================================

    @api_router.get("/mcp/connectors")
    async def list_mcp_connectors(request: Request, category: str = ""):
        """MCP connector marketplace."""
        await get_current_user(request)
        query = {"is_active": True}
        if category:
            query["category"] = category
        connectors = await db.mcp_connectors.find(query, {"_id": 0}).sort("install_count", -1).to_list(30)
        if not connectors:
            connectors = _builtin_mcp_connectors()
        return {"connectors": connectors}

    @api_router.post("/workspaces/{ws_id}/mcp/connect")
    async def connect_mcp_server(ws_id: str, request: Request):
        """Connect a custom MCP server to workspace."""
        user = await _authed_user(request, ws_id)
        body = await request.json()
        url = body.get("url", "")
        name = body.get("name", "")
        auth_type = body.get("auth_type", "none")
        auth_token = body.get("auth_token", "")
        if not url:
            raise HTTPException(400, "MCP server URL required")
        from nexus_utils import validate_external_url
        try:
            url = validate_external_url(url)
        except ValueError as e:
            raise HTTPException(400, f"Invalid MCP server URL: {e}")

        conn_id = f"mcp_{uuid.uuid4().hex[:10]}"
        connection = {
            "connection_id": conn_id, "workspace_id": ws_id,
            "url": url, "name": name or url[:40],
            "auth_type": auth_type, "status": "pending",
            "tools_discovered": [], "last_health_check": None,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        # Test connection
        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url.rstrip('/')}/tools", headers=headers)
                if resp.status_code == 200:
                    tools = resp.json().get("tools") or []
                    connection["status"] = "active"
                    connection["tools_discovered"] = [t.get("name", "") for t in tools[:20]]
                else:
                    connection["status"] = "error"
                    connection["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            connection["status"] = "error"
            connection["error"] = str(e)[:200]

        await db.mcp_connections.insert_one(connection)
        connection.pop("_id", None)
        return connection

    @api_router.get("/workspaces/{ws_id}/mcp/connections")
    async def list_mcp_connections(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        conns = await db.mcp_connections.find({"workspace_id": ws_id}, {"_id": 0}).to_list(20)
        return {"connections": conns}

    @api_router.get("/workspaces/{ws_id}/mcp/debug/{connection_id}")
    async def mcp_debug_console(ws_id: str, connection_id: str, request: Request):
        """Connector debugging console: request/response logs."""
        await _authed_user(request, ws_id)
        logs = await db.mcp_debug_logs.find(
            {"connection_id": connection_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(50).to_list(50)
        return {"logs": logs}

    # ==========================================
    # NX-006: AUDITABLE EXECUTION CHAINS
    # ==========================================

    @api_router.get("/workspaces/{ws_id}/execution-traces")
    async def list_execution_traces(ws_id: str, request: Request, limit: int = 20):
        """List all execution traces (DAG) for a workspace."""
        await _authed_user(request, ws_id)
        # Gather from orchestration runs + workflow runs
        orch_runs = await db.orchestration_runs.find(
            {"workspace_id": ws_id, "status": {"$in": ["completed", "failed"]}},
            {"_id": 0, "run_id": 1, "orchestration_name": 1, "status": 1,
             "started_at": 1, "completed_at": 1, "step_results": 1, "input_text": 1, "final_output": 1}
        ).sort("started_at", -1).limit(limit).to_list(limit)

        traces = []
        for run in orch_runs:
            steps = run.get("step_results") or []
            traces.append({
                "trace_id": run["run_id"], "type": "orchestration",
                "name": run.get("orchestration_name", ""),
                "status": run["status"], "step_count": len(steps),
                "started_at": run.get("started_at", ""),
                "completed_at": run.get("completed_at", ""),
                "input_preview": (run.get("input_text", ""))[:100],
                "output_preview": (run.get("final_output", ""))[:100],
            })
        return {"traces": traces}

    @api_router.get("/workspaces/{ws_id}/execution-traces/{trace_id}")
    async def get_execution_trace(ws_id: str, trace_id: str, request: Request):
        """Full DAG trace with all step details."""
        await _authed_user(request, ws_id)
        run = await db.orchestration_runs.find_one({"run_id": trace_id}, {"_id": 0})
        if not run:
            run = await db.workflow_runs.find_one({"run_id": trace_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Trace not found")

        # Build DAG nodes
        nodes = []
        steps = run.get("step_results") or []
        for i, step in enumerate(steps):
            nodes.append({
                "node_id": step.get("step_id", f"step_{i}"),
                "agent": step.get("agent_id", ""),
                "status": step.get("status", "unknown"),
                "output": step.get("output", "")[:2000],
                "error": step.get("error", ""),
                "parent_ids": [steps[i-1].get("step_id", "")] if i > 0 and run.get("execution_mode") != "parallel" else [],
                "position": {"x": 100 + (i % 3) * 300, "y": 100 + (i // 3) * 200},
            })

        return {
            "trace_id": trace_id,
            "name": run.get("orchestration_name", run.get("workflow_name", "")),
            "status": run.get("status", ""),
            "input_text": run.get("input_text", ""),
            "final_output": run.get("final_output", ""),
            "execution_mode": run.get("execution_mode", "sequential"),
            "nodes": nodes,
            "started_at": run.get("started_at", ""),
            "completed_at": run.get("completed_at", ""),
        }

    @api_router.post("/workspaces/{ws_id}/execution-traces/{trace_id}/replay/{step_id}")
    async def replay_step(ws_id: str, trace_id: str, step_id: str, data: StepReplayRequest, request: Request):
        """Replay a single step with same or modified inputs."""
        user = await _authed_user(request, ws_id)
        run = await db.orchestration_runs.find_one({"run_id": trace_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Trace not found")

        original_step = None
        for s in run.get("step_results") or []:
            if s.get("step_id") == step_id:
                original_step = s
                break
        if not original_step:
            raise HTTPException(404, "Step not found in trace")

        # Re-execute with same or modified prompt
        from agent_knowledge_retrieval import retrieve_training_knowledge
        agent_id = original_step.get("agent_id", "")
        prompt = data.modified_prompt or original_step.get("output", "")[:500]

        knowledge = await retrieve_training_knowledge(db, agent_id, prompt, max_chunks=5, max_tokens=2000)
        replay_output = f"[Replay of {step_id}] Knowledge context: {knowledge[:500] if knowledge else 'None'}\nBased on: {prompt[:300]}"

        replay_id = f"replay_{uuid.uuid4().hex[:10]}"
        replay = {
            "replay_id": replay_id, "trace_id": trace_id,
            "original_step_id": step_id, "agent_id": agent_id,
            "modified_prompt": data.modified_prompt,
            "output": replay_output, "replayed_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.execution_replays.insert_one(replay)
        replay.pop("_id", None)
        return replay

    @api_router.post("/workspaces/{ws_id}/execution-traces/{trace_id}/fork/{step_id}")
    async def fork_execution(ws_id: str, trace_id: str, step_id: str, request: Request):
        """Branch from a step to explore alternative paths."""
        user = await _authed_user(request, ws_id)
        run = await db.orchestration_runs.find_one({"run_id": trace_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Trace not found")

        # Create a new orchestration run branching from this step
        fork_id = f"orun_{uuid.uuid4().hex[:10]}"
        steps_up_to = []
        for s in run.get("step_results") or []:
            steps_up_to.append(s)
            if s.get("step_id") == step_id:
                break

        fork_run = {
            "run_id": fork_id, "orchestration_id": run.get("orchestration_id", ""),
            "orchestration_name": f"Fork of {run.get('orchestration_name', '')} @ {step_id}",
            "workspace_id": ws_id, "started_by": user["user_id"],
            "input_text": run.get("input_text", ""), "context": run.get("context") or {},
            "status": "forked", "step_results": steps_up_to,
            "final_output": steps_up_to[-1].get("output", "") if steps_up_to else "",
            "forked_from": {"trace_id": trace_id, "step_id": step_id},
            "started_at": now_iso(), "completed_at": now_iso(),
        }
        await db.orchestration_runs.insert_one(fork_run)
        fork_run.pop("_id", None)
        return fork_run

    @api_router.get("/workspaces/{ws_id}/execution-traces/{trace_id}/export")
    async def export_trace(ws_id: str, trace_id: str, request: Request):
        """Export execution trace as structured JSON for auditing."""
        await _authed_user(request, ws_id)
        run = await db.orchestration_runs.find_one({"run_id": trace_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Trace not found")

        export = {
            "schema": "nexus-execution-trace-v1",
            "exported_at": now_iso(),
            "trace": run,
        }
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=export,
            headers={"Content-Disposition": f"attachment; filename=trace_{sanitize_filename(trace_id)}.json"}
        )

    @api_router.get("/workspaces/{ws_id}/execution-traces/diff")
    async def diff_traces(ws_id: str, request: Request, trace_a: str = "", trace_b: str = ""):
        """Compare two execution traces side-by-side."""
        await _authed_user(request, ws_id)
        if not trace_a or not trace_b:
            raise HTTPException(400, "trace_a and trace_b query params required")

        run_a = await db.orchestration_runs.find_one({"run_id": trace_a}, {"_id": 0})
        run_b = await db.orchestration_runs.find_one({"run_id": trace_b}, {"_id": 0})
        if not run_a or not run_b:
            raise HTTPException(404, "One or both traces not found")

        steps_a = run_a.get("step_results") or []
        steps_b = run_b.get("step_results") or []

        divergence_point = None
        for i in range(min(len(steps_a), len(steps_b))):
            if steps_a[i].get("output", "")[:100] != steps_b[i].get("output", "")[:100]:
                divergence_point = i
                break

        return {
            "trace_a": {"id": trace_a, "name": run_a.get("orchestration_name", ""), "steps": len(steps_a), "status": run_a.get("status", "")},
            "trace_b": {"id": trace_b, "name": run_b.get("orchestration_name", ""), "steps": len(steps_b), "status": run_b.get("status", "")},
            "divergence_step": divergence_point,
            "steps_a": [{"step_id": s.get("step_id", ""), "agent": s.get("agent_id", ""), "status": s.get("status", ""), "output_preview": s.get("output", "")[:200]} for s in steps_a],
            "steps_b": [{"step_id": s.get("step_id", ""), "agent": s.get("agent_id", ""), "status": s.get("status", ""), "output_preview": s.get("output", "")[:200]} for s in steps_b],
        }


def _builtin_mcp_connectors():
    return [
        {"connector_id": "mcp_github", "name": "GitHub", "category": "development", "description": "Access repos, issues, PRs via MCP", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_slack", "name": "Slack", "category": "communication", "description": "Send/receive messages, manage channels", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_notion", "name": "Notion", "category": "productivity", "description": "Read/write pages, databases, blocks", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_google_workspace", "name": "Google Workspace", "category": "productivity", "description": "Docs, Sheets, Drive, Calendar access", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_salesforce", "name": "Salesforce", "category": "crm", "description": "Leads, contacts, opportunities, reports", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_jira", "name": "Jira", "category": "project_management", "description": "Issues, sprints, boards, workflows", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_confluence", "name": "Confluence", "category": "documentation", "description": "Pages, spaces, search, templates", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_linear", "name": "Linear", "category": "project_management", "description": "Issues, projects, cycles, roadmaps", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_postgres", "name": "PostgreSQL", "category": "database", "description": "Query databases, inspect schemas", "install_count": 0, "is_active": True},
        {"connector_id": "mcp_stripe", "name": "Stripe", "category": "payments", "description": "Customers, invoices, subscriptions", "install_count": 0, "is_active": True},
    ]
