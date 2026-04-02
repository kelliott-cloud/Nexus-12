"""Nexus × OpenClaw Bidirectional Integration — Bridge endpoints for messaging gateway."""
import uuid
import time
import logging
import hashlib
import os
from datetime import datetime, timezone
from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional
from nexus_utils import now_iso, safe_regex

logger = logging.getLogger(__name__)



def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


# ============ Auth Middleware ============

async def _validate_openclaw_token(db, request):
    """Validate Bearer token from OpenClaw gateway with rate limiting."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer nxoc_"):
        raise HTTPException(401, "Invalid OpenClaw token format. Expected: Bearer nxoc_...")
    token = auth.replace("Bearer ", "")
    token_hash = _hash_token(token)
    doc = await db.openclaw_tokens.find_one({"token_hash": token_hash, "revoked": False}, {"_id": 0})
    if not doc:
        raise HTTPException(401, "Invalid or revoked OpenClaw token")
    # Rate limiting with TTL-safe approach
    rate_limit = doc.get("rate_limit", 120)
    now = time.time()
    window_key = f"oc_rate_{doc['token_id']}"
    # Use update with $push + $pull for atomic rate limiting
    await db.openclaw_rate_limits.update_one(
        {"key": window_key},
        {"$push": {"timestamps": now}, "$pull": {"timestamps": {"$lt": now - 60}}},
        upsert=True,
    )
    rate_doc = await db.openclaw_rate_limits.find_one({"key": window_key}, {"_id": 0, "timestamps": 1})
    current_count = len(rate_doc.get("timestamps") or []) if rate_doc else 0
    if current_count > rate_limit:
        raise HTTPException(429, f"Rate limit exceeded ({rate_limit}/min)")
    await db.openclaw_tokens.update_one({"token_hash": token_hash}, {"$set": {"last_used_at": now_iso()}})
    return doc


def register_openclaw_routes(app, api_router, db, get_current_user):

    # ============ Health Check ============

    @api_router.get("/openclaw/health")
    async def openclaw_health():
        ws_count = await db.openclaw_tokens.count_documents({"revoked": False})
        sessions = await db.openclaw_sessions.count_documents({})
        return {"status": "ok", "version": "1.0.0", "connected_workspaces": ws_count, "active_sessions": sessions}

    # ============ Message Processing ============

    @api_router.post("/openclaw/message")
    async def process_message(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        body = await request.json()
        workspace_id = token_doc["workspace_id"]
        sender_id = body.get("sender_id", "")
        content = body.get("content", "")
        media_urls = body.get("media_urls") or []
        conversation_id = body.get("conversation_id")
        channel_type = body.get("channel_type", "unknown")

        if not sender_id or not content:
            raise HTTPException(400, "sender_id and content required")

        start = time.time()

        # Session management — find or create
        session = await db.openclaw_sessions.find_one(
            {"workspace_id": workspace_id, "sender_id": sender_id}, {"_id": 0}
        )
        if not session:
            session_id = f"ocs_{uuid.uuid4().hex[:12]}"
            conversation_id = conversation_id or f"occonv_{uuid.uuid4().hex[:10]}"
            session = {
                "session_id": session_id, "workspace_id": workspace_id,
                "sender_id": sender_id, "channel_type": channel_type,
                "conversation_id": conversation_id, "agent_id": None,
                "agent_history": [], "message_count": 0,
                "total_tokens": 0, "total_cost_usd": 0,
                "created_at": now_iso(), "last_activity": now_iso(), "metadata": {},
            }
            await db.openclaw_sessions.insert_one(session)
            session.pop("_id", None)
        else:
            session_id = session["session_id"]
            conversation_id = session.get("conversation_id", conversation_id)

        # Resolve agent — check channel mappings
        agent_id = session.get("agent_id")
        if not agent_id:
            mapping = await db.openclaw_channel_mappings.find_one(
                {"workspace_id": workspace_id, "active": True,
                 "$or": [{"sender_pattern": sender_id}, {"sender_pattern": "*"}, {"sender_pattern": channel_type}]},
                {"_id": 0}
            )
            if mapping:
                agent_id = mapping.get("agent_id", "auto")
            else:
                agent_id = "auto"

        # If auto, pick the first available agent or use chatgpt
        if agent_id == "auto":
            agents = await db.nexus_agents.find(
                {"workspace_id": workspace_id}, {"_id": 0, "agent_id": 1, "base_model": 1}
            ).limit(1).to_list(1)
            agent_id = agents[0]["agent_id"] if agents else "chatgpt"

        # Build context from conversation history
        history = await db.openclaw_message_log.find(
            {"session_id": session_id}, {"_id": 0, "direction": 1, "content": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        history.reverse()

        # Get agent config
        agent_config = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0})
        system_prompt = (agent_config or {}).get("system_prompt", "You are a helpful AI assistant connected via messaging.")
        base_model = (agent_config or {}).get("base_model", "chatgpt")

        # Inject knowledge if available
        try:
            from agent_knowledge_retrieval import retrieve_training_knowledge
            knowledge = await retrieve_training_knowledge(db, agent_id, content, max_chunks=5, max_tokens=2000)
            if knowledge:
                system_prompt += f"\n\n## Relevant Knowledge:\n{knowledge}"
        except Exception as _e:
            import logging; logging.getLogger("routes/routes_openclaw").warning(f"Suppressed: {_e}")

        # DataGuard: sanitize input
        try:
            from data_guard import DataGuard
            content = DataGuard.sanitize_input(content)
        except Exception as _e:
            import logging; logging.getLogger("routes/routes_openclaw").warning(f"Suppressed: {_e}")

        # Call AI
        from ai_providers import call_ai_direct
        from key_resolver import get_integration_key
        key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY",
                    "deepseek": "DEEPSEEK_API_KEY", "mistral": "MISTRAL_API_KEY"}
        api_key = await get_integration_key(db, key_map.get(base_model, "OPENAI_API_KEY"))
        if not api_key:
            api_key = os.environ.get(key_map.get(base_model, "OPENAI_API_KEY"), "")

        # Build messages for context
        context_prompt = content
        if history:
            context_parts = [f"{'User' if m['direction'] == 'inbound' else 'Assistant'}: {m['content'][:500]}" for m in history[-10:]]
            context_prompt = "\n".join(context_parts) + f"\nUser: {content}"

        try:
            response_text = await call_ai_direct(base_model, api_key, system_prompt, context_prompt)
        except Exception as ai_err:
            logger.error(f"OpenClaw AI call failed: {ai_err}")
            response_text = "I apologize, but I encountered an error processing your request. Please try again."
        latency_ms = int((time.time() - start) * 1000)
        tokens_in = len(context_prompt.split()) * 1.3
        tokens_out = len(response_text.split()) * 1.3
        from workflow_engine import calc_cost
        cost = calc_cost(base_model, int(tokens_in), int(tokens_out))

        # Log inbound message
        await db.openclaw_message_log.insert_one({
            "message_id": f"ocm_{uuid.uuid4().hex[:12]}", "session_id": session_id,
            "workspace_id": workspace_id, "direction": "inbound",
            "content": content, "media_urls": media_urls, "agent_id": agent_id,
            "model_used": None, "tokens_input": 0, "tokens_output": 0,
            "cost_usd": 0, "latency_ms": 0, "tools_used": [], "confidence_score": None,
            "created_at": now_iso(),
        })

        # Log outbound response
        await db.openclaw_message_log.insert_one({
            "message_id": f"ocm_{uuid.uuid4().hex[:12]}", "session_id": session_id,
            "workspace_id": workspace_id, "direction": "outbound",
            "content": response_text, "media_urls": [], "agent_id": agent_id,
            "model_used": base_model, "tokens_input": int(tokens_in), "tokens_output": int(tokens_out),
            "cost_usd": cost, "latency_ms": latency_ms, "tools_used": [], "confidence_score": None,
            "created_at": now_iso(),
        })

        # Update session
        await db.openclaw_sessions.update_one({"session_id": session_id}, {
            "$set": {"agent_id": agent_id, "last_activity": now_iso()},
            "$inc": {"message_count": 2, "total_tokens": int(tokens_in + tokens_out), "total_cost_usd": cost},
            "$addToSet": {"agent_history": agent_id},
        })

        return {
            "conversation_id": conversation_id, "response": response_text,
            "agent_id": agent_id, "model": base_model,
            "tokens": int(tokens_in + tokens_out), "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }

    # ============ Session Management ============

    @api_router.get("/openclaw/session")
    async def get_session(request: Request, sender_id: str = ""):
        token_doc = await _validate_openclaw_token(db, request)
        if not sender_id:
            raise HTTPException(400, "sender_id required")
        session = await db.openclaw_sessions.find_one(
            {"workspace_id": token_doc["workspace_id"], "sender_id": sender_id}, {"_id": 0}
        )
        if not session:
            return {"active": False}
        return {**session, "active": True}

    @api_router.post("/openclaw/session/reset")
    async def reset_session(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        body = await request.json()
        sender_id = body.get("sender_id", "")
        if not sender_id:
            raise HTTPException(400, "sender_id required")
        await db.openclaw_sessions.delete_one({"workspace_id": token_doc["workspace_id"], "sender_id": sender_id})
        return {"reset": True, "sender_id": sender_id}

    # ============ Agents ============

    @api_router.get("/openclaw/agents")
    async def list_agents(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        agents = await db.nexus_agents.find(
            {"workspace_id": token_doc["workspace_id"]},
            {"_id": 0, "agent_id": 1, "name": 1, "description": 1, "base_model": 1, "skills": 1, "status": 1}
        ).to_list(50)
        return {"agents": agents}

    # ============ Pipeline Trigger ============

    @api_router.post("/openclaw/pipelines/trigger")
    async def trigger_pipeline(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        body = await request.json()
        pipeline_id = body.get("pipeline_id", "")
        if not pipeline_id:
            raise HTTPException(400, "pipeline_id required")

        pipeline = await db.a2a_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": 0})
        if not pipeline:
            raise HTTPException(404, "Pipeline not found")

        run_id = f"a2a_run_{uuid.uuid4().hex[:12]}"
        run = {
            "run_id": run_id, "pipeline_id": pipeline_id,
            "workspace_id": token_doc["workspace_id"], "status": "running",
            "trigger_type": "openclaw", "trigger_payload": body.get("input_payload", ""),
            "current_step_id": None, "step_outputs": {},
            "total_cost_usd": 0, "total_tokens_in": 0, "total_tokens_out": 0,
            "total_duration_ms": 0, "started_at": now_iso(), "completed_at": None,
            "error": None, "created_by": "openclaw", "created_at": now_iso(),
        }
        await db.a2a_runs.insert_one(run)
        run.pop("_id", None)

        from a2a_engine import A2AEngine
        engine = A2AEngine(db)
        import asyncio
        asyncio.create_task(engine.execute_pipeline(run_id))

        return {"run_id": run_id, "status": "running"}

    @api_router.get("/openclaw/pipelines/{run_id}")
    async def pipeline_status(run_id: str, request: Request):
        await _validate_openclaw_token(db, request)
        run = await db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    # ============ Deployments ============

    @api_router.get("/openclaw/deployments")
    async def list_deployments(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        deps = await db.deployments.find(
            {"workspace_id": token_doc["workspace_id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"deployments": deps}

    # ============ Knowledge Search ============

    @api_router.post("/openclaw/knowledge/search")
    async def search_knowledge(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        body = await request.json()
        query = body.get("query", "")
        agent_id = body.get("agent_id")
        limit = min(body.get("limit", 10), 20)
        if not query:
            raise HTTPException(400, "query required")

        q = {"workspace_id": token_doc["workspace_id"], "flagged": {"$ne": True}}
        if agent_id:
            q["agent_id"] = agent_id

        chunks = await db.agent_knowledge.find(
            {**q, "content": {"$regex": safe_regex(query), "$options": "i"}},
            {"_id": 0, "content": 1, "topic": 1, "summary": 1, "quality_score": 1, "agent_id": 1}
        ).sort("quality_score", -1).limit(limit).to_list(limit)

        return {"results": chunks, "count": len(chunks), "query": query}

    # ============ Analytics ============

    @api_router.get("/openclaw/analytics")
    async def openclaw_analytics(request: Request, metric: str = "overview", time_range: str = "7d"):
        token_doc = await _validate_openclaw_token(db, request)
        ws_id = token_doc["workspace_id"]

        total_sessions = await db.openclaw_sessions.count_documents({"workspace_id": ws_id})
        total_messages = await db.openclaw_message_log.count_documents({"workspace_id": ws_id})

        agg = await db.openclaw_message_log.aggregate([
            {"$match": {"workspace_id": ws_id, "direction": "outbound"}},
            {"$group": {"_id": None, "total_cost": {"$sum": "$cost_usd"}, "total_tokens": {"$sum": {"$add": ["$tokens_input", "$tokens_output"]}}, "avg_latency": {"$avg": "$latency_ms"}}},
        ]).to_list(1)
        stats = agg[0] if agg else {}
        stats.pop("_id", None)

        return {
            "total_sessions": total_sessions, "total_messages": total_messages,
            "total_cost_usd": round(stats.get("total_cost", 0), 4),
            "total_tokens": stats.get("total_tokens", 0),
            "avg_latency_ms": int(stats.get("avg_latency", 0) or 0),
        }

    # ============ Notify (Outbound) ============

    @api_router.post("/openclaw/notify")
    async def send_notification(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        body = await request.json()
        sender_id = body.get("sender_id", "")
        channel = body.get("channel", "")
        message = body.get("message", "")
        if not sender_id or not message:
            raise HTTPException(400, "sender_id and message required")

        notification_id = f"ocn_{uuid.uuid4().hex[:12]}"
        await db.openclaw_notifications.insert_one({
            "notification_id": notification_id, "workspace_id": token_doc["workspace_id"],
            "sender_id": sender_id, "channel": channel, "message": message,
            "status": "pending", "created_at": now_iso(),
        })
        return {"notification_id": notification_id, "status": "queued"}

    # ============ Media Upload ============

    @api_router.post("/openclaw/media")
    async def upload_media(request: Request):
        token_doc = await _validate_openclaw_token(db, request)
        import base64
        body = await request.json()
        data = body.get("data", "")
        filename = body.get("filename", "upload")
        mime_type = body.get("mime_type", "application/octet-stream")
        media_id = f"ocmed_{uuid.uuid4().hex[:12]}"
        await db.openclaw_media.insert_one({
            "media_id": media_id, "workspace_id": token_doc["workspace_id"],
            "filename": filename, "mime_type": mime_type,
            "data": data[:5000000], "created_at": now_iso(),
        })
        return {"media_id": media_id, "url": f"/api/openclaw/media/{media_id}"}

    @api_router.get("/openclaw/media/{media_id}")
    async def get_media(media_id: str, request: Request):
        doc = await db.openclaw_media.find_one({"media_id": media_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Media not found")
        return {"media_id": media_id, "filename": doc.get("filename"), "mime_type": doc.get("mime_type")}

    # ============ Admin: Token Management (Nexus UI) ============

    @api_router.post("/openclaw/tokens")
    async def create_token(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        workspace_id = body.get("workspace_id", "")
        label = body.get("label", "OpenClaw Gateway")
        permissions = body.get("permissions", ["message", "session", "agents", "pipeline", "knowledge", "analytics", "notify"])
        rate_limit = body.get("rate_limit", 120)

        import secrets
        raw_token = f"nxoc_{secrets.token_urlsafe(48)}"
        token_hash = _hash_token(raw_token)

        doc = {
            "token_id": f"oct_{uuid.uuid4().hex[:12]}",
            "token_hash": token_hash, "workspace_id": workspace_id,
            "label": label, "permissions": permissions,
            "rate_limit": rate_limit, "created_by": user["user_id"],
            "created_at": now_iso(), "last_used_at": None, "revoked": False,
        }
        await db.openclaw_tokens.insert_one(doc)
        doc.pop("_id", None)
        doc["token"] = raw_token  # Only returned once
        doc.pop("token_hash", None)
        return doc

    @api_router.get("/openclaw/tokens")
    async def list_tokens(request: Request):
        user = await get_current_user(request)
        tokens = await db.openclaw_tokens.find(
            {"created_by": user["user_id"]},
            {"_id": 0, "token_hash": 0}
        ).sort("created_at", -1).to_list(20)
        return {"tokens": tokens}

    @api_router.delete("/openclaw/tokens/{token_id}")
    async def revoke_token(token_id: str, request: Request):
        await get_current_user(request)
        await db.openclaw_tokens.update_one({"token_id": token_id}, {"$set": {"revoked": True}})
        return {"revoked": True}

    # ============ Admin: Channel Mappings ============

    @api_router.get("/openclaw/mappings/{workspace_id}")
    async def list_mappings(workspace_id: str, request: Request):
        await get_current_user(request)
        mappings = await db.openclaw_channel_mappings.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("priority", -1).to_list(20)
        return {"mappings": mappings}

    @api_router.post("/openclaw/mappings")
    async def create_mapping(request: Request):
        await get_current_user(request)
        body = await request.json()
        mapping_id = f"ocmap_{uuid.uuid4().hex[:10]}"
        mapping = {
            "mapping_id": mapping_id,
            "workspace_id": body.get("workspace_id", ""),
            "sender_pattern": body.get("sender_pattern", "*"),
            "agent_id": body.get("agent_id", "auto"),
            "channel_id": body.get("channel_id", ""),
            "priority": body.get("priority", 0),
            "active": True, "created_at": now_iso(),
        }
        await db.openclaw_channel_mappings.insert_one(mapping)
        mapping.pop("_id", None)
        return mapping

    @api_router.delete("/openclaw/mappings/{mapping_id}")
    async def delete_mapping(mapping_id: str, request: Request):
        await get_current_user(request)
        await db.openclaw_channel_mappings.delete_one({"mapping_id": mapping_id})
        return {"deleted": True}

    # ============ Admin: Activity Log ============

    @api_router.get("/openclaw/activity/{workspace_id}")
    async def activity_log(workspace_id: str, request: Request, limit: int = 50):
        await get_current_user(request)
        logs = await db.openclaw_message_log.find(
            {"workspace_id": workspace_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"messages": logs}
