"""Keystone Feature Routes — Consensus, Workspace-as-Code, Cost Arbitrage, GDPR, Key Rotation."""
import uuid
import json
import yaml
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from fastapi.responses import Response
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



def register_keystone_routes(api_router, db, get_current_user):

    # ============ A1: Consensus Engine ============

    @api_router.post("/channels/{channel_id}/consensus/trigger")
    async def trigger_consensus(channel_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_channel_access
        await require_channel_access(db, user, channel_id)
        session_id = f"cns_{uuid.uuid4().hex[:12]}"
        # Get recent AI messages with differing positions
        msgs = await db.messages.find(
            {"channel_id": channel_id, "sender_type": "ai"},
            {"_id": 0, "agent": 1, "content": 1, "created_at": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        msgs.reverse()

        if len(msgs) < 2:
            raise HTTPException(400, "Need at least 2 AI responses to analyze consensus")

        # Build agent responses for analysis
        agent_positions = {}
        for m in msgs:
            agent = m.get("agent", "unknown")
            agent_positions.setdefault(agent, []).append(m.get("content", "")[:1000])

        session = {
            "session_id": session_id, "channel_id": channel_id,
            "workspace_id": (await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1}) or {}).get("workspace_id", ""),
            "trigger": "manual", "status": "analyzing",
            "agent_positions": {a: ps[-1] for a, ps in agent_positions.items()},
            "disputed_claims": [], "resolution_rounds": [],
            "synthesis": None, "created_at": now_iso(), "completed_at": None,
        }
        await db.consensus_sessions.insert_one(session)
        session.pop("_id", None)

        # Run analysis in background
        from keystone import event_bus
        await event_bus.emit("consensus.triggered", {"session_id": session_id, "channel_id": channel_id})

        return session

    @api_router.get("/channels/{channel_id}/consensus/latest")
    async def get_latest_consensus(channel_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_channel_access
        await require_channel_access(db, user, channel_id)
        session = await db.consensus_sessions.find_one(
            {"channel_id": channel_id}, {"_id": 0},
            sort=[("created_at", -1)]
        )
        if not session:
            return {"active": False}
        return session

    @api_router.get("/consensus/{session_id}")
    async def get_consensus(session_id: str, request: Request):
        await get_current_user(request)
        session = await db.consensus_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Consensus session not found")
        return session

    # ============ A2: Workspace-as-Code ============

    @api_router.post("/workspaces/{ws_id}/export")
    async def export_workspace(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not ws:
            raise HTTPException(404, "Workspace not found")

        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0, "name": 1, "ai_agents": 1, "disabled_agents": 1, "auto_collab_enabled": 1}).to_list(50)
        agents = await db.nexus_agents.find({"workspace_id": ws_id}, {"_id": 0, "name": 1, "base_model": 1, "system_prompt": 1, "skills": 1, "description": 1}).to_list(20)
        pipelines = await db.a2a_pipelines.find({"workspace_id": ws_id}, {"_id": 0, "name": 1, "steps": 1, "settings": 1, "triggers": 1}).to_list(20)

        manifest = {
            "schema_version": "1.0",
            "name": ws.get("name", ""),
            "description": ws.get("description", ""),
            "modules": (ws.get("module_config") or {}).get("modules") or {},
            "ai_models": (ws.get("module_config") or {}).get("ai_models") or [],
            "agents": [{"name": a.get("name"), "base_model": a.get("base_model"), "system_prompt": a.get("system_prompt", ""), "skills": a.get("skills") or [], "description": a.get("description", "")} for a in agents],
            "channels": [{"name": c.get("name"), "agents": c.get("ai_agents") or [], "auto_collab": c.get("auto_collab_enabled", False)} for c in channels],
            "pipelines": [{"name": p.get("name"), "steps": p.get("steps") or [], "settings": p.get("settings") or {}} for p in pipelines],
            "exported_at": now_iso(),
            "exported_by": user["user_id"],
        }

        yaml_content = yaml.dump(manifest, default_flow_style=False, sort_keys=False)
        from nexus_utils import sanitize_filename
        return Response(content=yaml_content, media_type="application/x-yaml",
                        headers={"Content-Disposition": f"attachment; filename=nexus_{sanitize_filename(ws_id)}.yaml"})

    @api_router.post("/workspaces/import")
    async def import_workspace(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        manifest_str = body.get("manifest", "")
        if not manifest_str:
            raise HTTPException(400, "manifest YAML string required")
        try:
            manifest = yaml.safe_load(manifest_str)
        except Exception as e:
            raise HTTPException(400, f"Invalid YAML: {str(e)[:200]}")

        # Schema validation
        if not isinstance(manifest, dict):
            raise HTTPException(400, "Manifest must be a YAML mapping")
        required = ["name"]
        for field in required:
            if field not in manifest:
                raise HTTPException(400, f"Manifest missing required field: {field}")
        if manifest.get("schema_version") and manifest["schema_version"] not in ("1.0",):
            raise HTTPException(400, f"Unsupported schema version: {manifest['schema_version']}")
        # Validate arrays
        for arr_field in ["agents", "channels", "pipelines"]:
            if arr_field in manifest and not isinstance(manifest[arr_field], list):
                raise HTTPException(400, f"'{arr_field}' must be an array")

        ws_id = f"ws_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        ws = {
            "workspace_id": ws_id, "name": manifest.get("name", "Imported Workspace"),
            "description": manifest.get("description", ""), "owner_id": user["user_id"],
            "members": [user["user_id"]], "module_config": {"modules": manifest.get("modules") or {}, "ai_models": manifest.get("ai_models") or [], "wizard_completed": True},
            "created_at": now, "imported_from_manifest": True,
        }
        await db.workspaces.insert_one(ws)

        created = {"workspace_id": ws_id, "agents": [], "channels": [], "pipelines": []}

        SAFE_AGENT_FIELDS = {"name", "base_model", "system_prompt", "skills", "description", "personality", "guardrails", "allowed_tools", "denied_tools"}
        for a in manifest.get("agents") or []:
            aid = f"nxa_{uuid.uuid4().hex[:12]}"
            clean = {k: v for k, v in a.items() if k in SAFE_AGENT_FIELDS and not str(k).startswith("$")}
            await db.nexus_agents.insert_one({**clean, "agent_id": aid, "workspace_id": ws_id, "created_at": now, "created_by": user["user_id"]})
            created["agents"].append(aid)

        for c in manifest.get("channels") or []:
            cid = f"ch_{uuid.uuid4().hex[:12]}"
            await db.channels.insert_one({"channel_id": cid, "workspace_id": ws_id, "name": c.get("name", ""), "ai_agents": c.get("agents") or [], "auto_collab_enabled": c.get("auto_collab", False), "created_at": now})
            created["channels"].append(cid)

        for p in manifest.get("pipelines") or []:
            pid = f"a2a_pip_{uuid.uuid4().hex[:12]}"
            await db.a2a_pipelines.insert_one({"pipeline_id": pid, "workspace_id": ws_id, "name": p.get("name", ""), "steps": p.get("steps") or [], "settings": p.get("settings") or {}, "status": "draft", "created_at": now})
            created["pipelines"].append(pid)

        return created

    @api_router.get("/workspaces/{ws_id}/manifest")
    async def get_manifest(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return await _build_manifest(db, ws_id)

    async def _build_manifest(db, ws_id):
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        agents = await db.nexus_agents.find({"workspace_id": ws_id}, {"_id": 0, "name": 1, "base_model": 1, "skills": 1}).to_list(20)
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0, "name": 1, "ai_agents": 1}).to_list(50)
        return {"schema_version": "1.0", "name": (ws or {}).get("name", ""), "agents": agents, "channels": channels, "modules": ((ws or {}).get("module_config") or {}).get("modules") or {}}

    # ============ A3: Cost Arbitrage Controls ============

    @api_router.get("/workspaces/{ws_id}/cost-arbitrage/config")
    async def get_arbitrage_config(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        config = await db.workspace_settings.find_one({"workspace_id": ws_id}, {"_id": 0, "cost_arbitrage": 1})
        return (config or {}).get("cost_arbitrage", {"routing_mode": "manual", "quality_threshold": 0.7, "monthly_budget_usd": 100, "show_routing_badge": True, "excluded_models": [], "force_premium_channels": []})

    @api_router.put("/workspaces/{ws_id}/cost-arbitrage/config")
    async def update_arbitrage_config(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        updates = {}
        for f in ["routing_mode", "quality_threshold", "monthly_budget_usd", "show_routing_badge", "excluded_models", "force_premium_channels"]:
            if f in body:
                val = body[f]
                if f == "quality_threshold":
                    val = max(0.0, min(1.0, float(val)))
                if f == "monthly_budget_usd":
                    val = max(0, float(val))
                if f == "routing_mode" and val not in ("manual", "auto_cheapest", "auto_balanced", "auto_quality"):
                    raise HTTPException(400, f"Invalid routing_mode: {val}")
                updates[f"cost_arbitrage.{f}"] = val
        if updates:
            await db.workspace_settings.update_one({"workspace_id": ws_id}, {"$set": updates}, upsert=True)
        return {"updated": True}

    @api_router.post("/workspaces/{ws_id}/cost-arbitrage/route")
    async def route_request(ws_id: str, request: Request):
        """Get the optimal model for a prompt based on cost arbitrage rules."""
        user = await get_current_user(request)
        body = await request.json()
        prompt = body.get("prompt", "")
        from keystone import classify_task, select_cheapest_model
        task_type = classify_task(prompt)
        config = await db.workspace_settings.find_one({"workspace_id": ws_id}, {"_id": 0, "cost_arbitrage": 1})
        arb = (config or {}).get("cost_arbitrage") or {}
        quality_threshold = arb.get("quality_threshold", 0.7)
        excluded = arb.get("excluded_models") or []
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "module_config": 1})
        enabled = [m for m in ((ws or {}).get("module_config") or {}).get("ai_models", ["chatgpt", "claude", "gemini"]) if m not in excluded]
        model, quality, cost = select_cheapest_model(task_type, enabled, quality_threshold)
        premium_cost = 0.005
        savings = round(max(premium_cost - cost, 0) * (len(prompt.split()) * 1.3 / 1000), 6)
        return {"task_type": task_type, "selected_model": model, "quality_score": quality, "cost_per_1k": cost, "savings_usd": savings, "candidates_checked": len(enabled)}

    # ============ B3: GDPR Erasure ============

    @api_router.post("/admin/gdpr/erase/{user_id}")
    async def gdpr_erase_user(user_id: str, request: Request):
        admin = await get_current_user(request)
        if admin.get("platform_role") not in ("super_admin",):
            raise HTTPException(403, "Super admin only")
        # Check cooling period
        pending = await db.deletion_requests.find_one(
            {"user_id": user_id, "status": "pending"}, {"_id": 0, "cooling_period_ends": 1}
        )
        if pending:
            ends = pending.get("cooling_period_ends", "")
            if ends > now_iso():
                raise HTTPException(400, f"Cooling period active until {ends}. Cannot erase yet.")
        from keystone import erase_user
        result = await erase_user(db, user_id, reason="admin_request")
        await db.deletion_requests.update_many({"user_id": user_id}, {"$set": {"status": "completed", "erased_at": now_iso()}})
        return result

    @api_router.post("/account/request-deletion")
    async def request_self_deletion(request: Request):
        user = await get_current_user(request)
        await db.deletion_requests.insert_one({
            "request_id": f"del_{uuid.uuid4().hex[:10]}", "user_id": user["user_id"],
            "email": user.get("email", ""), "status": "pending",
            "cooling_period_ends": (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
            "created_at": now_iso(),
        })
        return {"status": "pending", "cooling_period_hours": 72, "message": "Your deletion request has been submitted. Data will be erased after 72 hours."}

    # ============ B5: Key Rotation ============

    @api_router.post("/developer/api-keys/{key_id}/rotate")
    async def rotate_api_key(key_id: str, request: Request):
        user = await get_current_user(request)
        # Verify ownership
        key_doc = await db.developer_api_keys.find_one({"key_id": key_id}, {"_id": 0, "user_id": 1, "revoked": 1})
        if not key_doc:
            raise HTTPException(404, "Key not found")
        if key_doc.get("user_id") != user["user_id"] and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Not your key")
        if key_doc.get("revoked"):
            raise HTTPException(400, "Cannot rotate a revoked key")
        from keystone import rotate_key
        result = await rotate_key(db, key_id, user["user_id"])
        if not result:
            raise HTTPException(500, "Rotation failed")
        return result

    # ============ Circuit Breaker Status ============

    @api_router.get("/admin/circuit-breaker")
    async def circuit_breaker_status(request: Request):
        await get_current_user(request)
        from keystone import circuit_breaker
        return {"providers": circuit_breaker.get_status()}

    # ============ Billing Usage Check ============

    @api_router.get("/billing/usage-check")
    async def check_billing_usage(request: Request):
        user = await get_current_user(request)
        from keystone import check_usage, METERED_ACTIONS
        results = {}
        for action in METERED_ACTIONS:
            allowed = await check_usage(db, user["user_id"], action)
            results[action] = {"allowed": allowed}
        return {"user_id": user["user_id"], "plan": user.get("plan", "free"), "usage": results}
