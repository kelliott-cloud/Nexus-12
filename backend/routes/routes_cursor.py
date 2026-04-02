"""Nexus × Cursor 2 AI Integration — Cloud Agent API, MCP Server, AI Model Provider."""
import uuid
import json
import re
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)



# ============ Cloud Agent API Client ============

async def call_cursor_agent(api_key, prompt, workspace_context="", max_turns=10):
    """Call Cursor Cloud Agent API for code generation/editing tasks."""
    import httpx
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Create agent session
        resp = await client.post(
            "https://api.cursor.com/v1/agents/create",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "prompt": prompt,
                "context": workspace_context[:50000],
                "max_turns": max_turns,
                "model": "composer",
            }
        )
        if resp.status_code != 200:
            raise Exception(f"Cursor Agent API error: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        agent_id = data.get("agent_id", "")

        # Poll for completion
        for _ in range(60):
            status_resp = await client.get(
                f"https://api.cursor.com/v1/agents/{agent_id}/status",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if status_resp.status_code != 200:
                break
            status = status_resp.json()
            if status.get("status") in ("completed", "failed"):
                return status
            await asyncio.sleep(2)

        return {"status": "timeout", "agent_id": agent_id}


def register_cursor_routes(api_router, db, get_current_user):

    # ============ Cloud Agent Trigger ============

    @api_router.post("/workspaces/{ws_id}/cursor/agent")
    async def trigger_cursor_agent(ws_id: str, request: Request):
        """Trigger a Cursor Cloud Agent for code generation/editing."""
        user = await get_current_user(request)
        from nexus_utils import validate_external_url, now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        prompt = body.get("prompt", "")
        if not prompt:
            raise HTTPException(400, "prompt required")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "CURSOR_API_KEY")
        if not api_key:
            api_key = os.environ.get("CURSOR_API_KEY", "")
        if not api_key:
            raise HTTPException(503, "Cursor API key not configured. Add CURSOR_API_KEY in Settings → AI Keys.")

        # Build workspace context
        context_parts = []
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0, "name": 1}).to_list(5)
        context_parts.append(f"Workspace channels: {[c.get('name','') for c in channels]}")

        # Recent code files
        repo_files = await db.repo_files.find(
            {"workspace_id": ws_id, "is_deleted": {"$ne": True}},
            {"_id": 0, "path": 1, "language": 1}
        ).sort("updated_at", -1).limit(20).to_list(20)
        if repo_files:
            context_parts.append(f"Recent code files: {[f.get('path','') for f in repo_files]}")

        workspace_context = "\n".join(context_parts)

        # Log the request
        session_id = f"crs_{uuid.uuid4().hex[:12]}"
        await db.cursor_sessions.insert_one({
            "session_id": session_id, "workspace_id": ws_id,
            "prompt": prompt[:2000], "status": "running",
            "user_id": user["user_id"], "created_at": now_iso(),
            "result": None, "artifacts": [],
        })

        try:
            result = await call_cursor_agent(api_key, prompt, workspace_context)
            status = result.get("status", "unknown")
            await db.cursor_sessions.update_one({"session_id": session_id}, {"$set": {
                "status": status, "result": result, "completed_at": now_iso(),
            }})
            return {"session_id": session_id, "status": status, "result": result}
        except Exception as e:
            await db.cursor_sessions.update_one({"session_id": session_id}, {"$set": {
                "status": "failed", "error": str(e)[:500], "completed_at": now_iso(),
            }})
            raise HTTPException(502, f"Cursor Agent failed: {str(e)[:200]}")

    @api_router.get("/workspaces/{ws_id}/cursor/sessions")
    async def list_cursor_sessions(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        sessions = await db.cursor_sessions.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"sessions": sessions}

    @api_router.get("/cursor/sessions/{session_id}/artifacts")
    async def get_cursor_artifacts(session_id: str, request: Request):
        user = await get_current_user(request)
        session = await db.cursor_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Session not found")
        ws_id = session.get("workspace_id", "")
        if ws_id:
            from nexus_utils import now_iso, require_workspace_access
            await require_workspace_access(db, user, ws_id)
        return {"artifacts": session.get("artifacts") or [], "result": session.get("result")}

    # ============ MCP Server (Cursor connects to Nexus) ============

    @api_router.get("/cursor/mcp/tools")
    async def mcp_list_tools(request: Request):
        """MCP tool discovery — Cursor calls this to see available Nexus tools."""
        # Auth via Cursor's MCP token or user session
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer nxapi_"):
            import hashlib
            key_hash = hashlib.sha256(auth.replace("Bearer ", "").encode()).hexdigest()
            key_doc = await db.developer_api_keys.find_one({"key_hash": key_hash, "revoked": False}, {"_id": 0})
            if not key_doc:
                raise HTTPException(401, "Invalid API key")
        else:
            await get_current_user(request)

        return {"tools": [
            {"name": "nexus_search_knowledge", "description": "Search agent knowledge base for relevant information", "parameters": {"query": {"type": "string", "required": True}, "agent_id": {"type": "string"}, "limit": {"type": "integer"}}},
            {"name": "nexus_list_agents", "description": "List available AI agents in the workspace", "parameters": {"workspace_id": {"type": "string", "required": True}}},
            {"name": "nexus_send_message", "description": "Send a message to a Nexus channel", "parameters": {"channel_id": {"type": "string", "required": True}, "content": {"type": "string", "required": True}}},
            {"name": "nexus_get_code_files", "description": "List code files in the workspace repository", "parameters": {"workspace_id": {"type": "string", "required": True}, "path": {"type": "string"}}},
            {"name": "nexus_read_code_file", "description": "Read a specific code file from the repository", "parameters": {"workspace_id": {"type": "string", "required": True}, "file_path": {"type": "string", "required": True}}},
            {"name": "nexus_write_code_file", "description": "Write/update a code file in the repository", "parameters": {"workspace_id": {"type": "string", "required": True}, "file_path": {"type": "string", "required": True}, "content": {"type": "string", "required": True}}},
            {"name": "nexus_create_task", "description": "Create a project task", "parameters": {"workspace_id": {"type": "string", "required": True}, "title": {"type": "string", "required": True}, "description": {"type": "string"}}},
            {"name": "nexus_search_wiki", "description": "Search workspace wiki/docs", "parameters": {"workspace_id": {"type": "string", "required": True}, "query": {"type": "string", "required": True}}},
            {"name": "nexus_trigger_pipeline", "description": "Trigger an A2A pipeline", "parameters": {"pipeline_id": {"type": "string", "required": True}, "payload": {"type": "string"}}},
        ]}

    @api_router.post("/cursor/mcp/invoke")
    async def mcp_invoke_tool(request: Request):
        """MCP tool invocation — Cursor calls this to execute a Nexus tool."""
        auth = request.headers.get("Authorization", "")
        user_id = None
        workspace_id = None

        if auth.startswith("Bearer nxapi_"):
            import hashlib
            key_hash = hashlib.sha256(auth.replace("Bearer ", "").encode()).hexdigest()
            key_doc = await db.developer_api_keys.find_one({"key_hash": key_hash, "revoked": False}, {"_id": 0})
            if not key_doc:
                raise HTTPException(401, "Invalid API key")
            user_id = key_doc.get("user_id")
            workspace_id = key_doc.get("workspace_id")
        else:
            user = await get_current_user(request)
            user_id = user["user_id"]

        body = await request.json()
        tool_name = body.get("tool", "")
        params = body.get("params") or {}
        ws_id = params.get("workspace_id") or workspace_id

        # C26: Verify workspace access before ANY tool operation
        if not ws_id:
            raise HTTPException(400, "workspace_id is required")
        from data_guard import TenantIsolation
        has_access = await TenantIsolation.verify_workspace_access(db, user_id, ws_id)
        if not has_access:
            raise HTTPException(403, "Workspace access denied")

        if tool_name == "nexus_search_knowledge":
            from nexus_utils import now_iso, safe_regex
            query = params.get("query", "")
            agent_id = params.get("agent_id")
            q = {"flagged": {"$ne": True}, "content": {"$regex": safe_regex(query), "$options": "i"}}
            if agent_id:
                q["agent_id"] = agent_id
            if ws_id:
                q["workspace_id"] = ws_id
            chunks = await db.agent_knowledge.find(q, {"_id": 0, "content": 1, "topic": 1, "summary": 1}).sort("quality_score", -1).limit(params.get("limit", 10)).to_list(10)
            return {"result": chunks}

        elif tool_name == "nexus_list_agents":
            agents = await db.nexus_agents.find({"workspace_id": ws_id}, {"_id": 0, "agent_id": 1, "name": 1, "description": 1, "base_model": 1}).to_list(20)
            return {"result": agents}

        elif tool_name == "nexus_send_message":
            channel_id = params.get("channel_id", "")
            content = params.get("content", "")
            if not channel_id:
                return {"error": "channel_id required"}
            # Verify channel belongs to the authorized workspace
            channel = await db.channels.find_one({"channel_id": channel_id, "workspace_id": ws_id}, {"_id": 0, "channel_id": 1})
            if not channel:
                return {"error": "Channel not found in this workspace"}
            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            await db.messages.insert_one({"message_id": msg_id, "channel_id": channel_id, "workspace_id": ws_id, "content": content, "sender_name": "Cursor Agent", "sender_type": "ai", "created_at": now_iso()})
            return {"result": {"message_id": msg_id}}

        elif tool_name == "nexus_get_code_files":
            path = params.get("path", "/")
            escaped_path = re.escape(path)
            files = await db.repo_files.find({"workspace_id": ws_id, "path": {"$regex": f"^{escaped_path}"}, "is_deleted": {"$ne": True}}, {"_id": 0, "path": 1, "language": 1, "is_folder": 1}).limit(50).to_list(50)
            return {"result": files}

        elif tool_name == "nexus_read_code_file":
            file_path = params.get("file_path", "")
            f = await db.repo_files.find_one({"workspace_id": ws_id, "path": file_path, "is_deleted": {"$ne": True}}, {"_id": 0, "content": 1, "path": 1, "language": 1})
            return {"result": f or {"error": "File not found"}}

        elif tool_name == "nexus_write_code_file":
            file_path = params.get("file_path", "")
            content = params.get("content", "")
            await db.repo_files.update_one({"workspace_id": ws_id, "path": file_path}, {"$set": {"content": content, "updated_at": now_iso(), "updated_by": user_id}}, upsert=True)
            return {"result": {"written": file_path}}

        elif tool_name == "nexus_create_task":
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            await db.project_tasks.insert_one({"task_id": task_id, "workspace_id": ws_id, "title": params.get("title", ""), "description": params.get("description", ""), "status": "todo", "created_by": user_id, "created_at": now_iso()})
            return {"result": {"task_id": task_id}}

        elif tool_name == "nexus_search_wiki":
            from nexus_utils import now_iso, safe_regex
            query = params.get("query", "")
            pages = await db.wiki_pages.find({"workspace_id": ws_id, "is_deleted": {"$ne": True}, "$or": [{"title": {"$regex": safe_regex(query), "$options": "i"}}, {"content": {"$regex": safe_regex(query), "$options": "i"}}]}, {"_id": 0, "page_id": 1, "title": 1}).limit(10).to_list(10)
            return {"result": pages}

        elif tool_name == "nexus_trigger_pipeline":
            pipeline_id = params.get("pipeline_id", "")
            run_id = f"a2a_run_{uuid.uuid4().hex[:12]}"
            await db.a2a_runs.insert_one({"run_id": run_id, "pipeline_id": pipeline_id, "workspace_id": ws_id, "status": "running", "trigger_type": "cursor_mcp", "trigger_payload": params.get("payload", ""), "current_step_id": None, "step_outputs": {}, "total_cost_usd": 0, "total_tokens_in": 0, "total_tokens_out": 0, "total_duration_ms": 0, "started_at": now_iso(), "completed_at": None, "error": None, "created_by": user_id, "created_at": now_iso()})
            from a2a_engine import A2AEngine
            import asyncio
            engine = A2AEngine(db)
            asyncio.create_task(engine.execute_pipeline(run_id))
            return {"result": {"run_id": run_id, "status": "running"}}

        else:
            raise HTTPException(400, f"Unknown tool: {tool_name}")

    # ============ MCP Config Generator ============

    @api_router.get("/cursor/mcp/config")
    async def generate_mcp_config(request: Request):
        """Generate mcp.json config for Cursor IDE."""
        user = await get_current_user(request)
        api_url = os.environ.get("APP_URL", request.headers.get("origin", ""))
        return {
            "instructions": "Add this to your Cursor project's .cursor/mcp.json file",
            "config": {
                "mcpServers": {
                    "nexus-cloud": {
                        "url": f"{api_url}/api/cursor/mcp",
                        "headers": {
                            "Authorization": "Bearer nxapi_YOUR_API_KEY_HERE"
                        },
                        "description": "Nexus Cloud — AI agents, knowledge base, code repo, wiki, pipelines"
                    }
                }
            },
            "note": "Generate an API key at Settings → Developer API, then paste it above."
        }

    # ============ Cursor Analytics ============

    @api_router.get("/workspaces/{ws_id}/cursor/analytics")
    async def cursor_analytics(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        total = await db.cursor_sessions.count_documents({"workspace_id": ws_id})
        completed = await db.cursor_sessions.count_documents({"workspace_id": ws_id, "status": "completed"})
        failed = await db.cursor_sessions.count_documents({"workspace_id": ws_id, "status": "failed"})
        return {"total_sessions": total, "completed": completed, "failed": failed, "success_rate": round(completed / max(total, 1) * 100, 1)}
