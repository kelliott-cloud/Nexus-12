"""Extracted from server.py — auto-generated module."""
import os
import uuid
import secrets
import asyncio
import logging
import time
import httpx
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

from nexus_utils import sanitize_html

def register_workspaces_routes(api_router, db, get_current_user):
    from nexus_models import SessionExchange, WorkspaceCreate, ChannelCreate, MessageCreate, WorkspaceUpdate, ChannelUpdate

    async def _resolve_workspace_agent_health(user: dict, workspace: dict, channel_id: str | None = None):
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace["workspace_id"])
        from managed_keys import assess_ai_provider_key_health
        from routes_ai_keys import decrypt_key

        agents = []
        if channel_id:
            channel = await db.channels.find_one({"channel_id": channel_id, "workspace_id": workspace["workspace_id"]}, {"_id": 0, "ai_agents": 1})
            agents = channel.get("ai_agents") or [] if channel else []
        if not agents:
            agents = list({agent for ch in await db.channels.find({"workspace_id": workspace["workspace_id"]}, {"_id": 0, "ai_agents": 1}).to_list(100) for agent in (ch.get("ai_agents") or [])})

        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_keys": 1, "managed_keys_optin": 1}) or {}
        ai_config = workspace.get("ai_config") or {}
        warnings = []
        providers = {}

        for agent in agents:
            effective_agent = agent
            if agent.startswith("nxa_"):
                custom = await db.nexus_agents.find_one({"agent_id": agent, "workspace_id": workspace["workspace_id"]}, {"_id": 0, "base_model": 1})
                effective_agent = (custom or {}).get("base_model", agent)
            if effective_agent in providers:
                continue

            source = "none"
            project_cfg = (ai_config.get(effective_agent) or {}) if ai_config else {}
            if project_cfg.get("key_source") == "project" and project_cfg.get("api_key_encrypted"):
                try:
                    if decrypt_key(project_cfg["api_key_encrypted"]):
                        source = "project"
                except Exception:
                    source = "project_invalid"

            if source == "none":
                user_key = ((user_doc.get("ai_keys") or {}).get(effective_agent))
                if user_key:
                    try:
                        if decrypt_key(user_key):
                            source = "account"
                    except Exception:
                        source = "account_invalid"

            health = await assess_ai_provider_key_health(effective_agent)
            if source == "none" and (user_doc.get("managed_keys_optin") or {}).get(effective_agent, False):
                source = "platform"

            providers[effective_agent] = {
                "provider": effective_agent,
                "source": source,
                "platform_health": health,
            }

            if source == "platform" and health.get("status") in {"placeholder", "invalid"}:
                warnings.append({
                    "provider": effective_agent,
                    "message": health.get("message") or "Platform key is unhealthy",
                })

        return {
            "has_warning": bool(warnings),
            "warnings": warnings,
            "providers": providers,
            "channel_id": channel_id,
        }

    
    @api_router.get("/workspaces")
    async def get_workspaces(request: Request, include_disabled: bool = False, search: str = ""):
        user = await get_current_user(request)
        
        # Super admins see all workspaces
        is_admin = user.get("platform_role") == "super_admin"
        if is_admin:
            ownership_filter = {}
        else:
            member_docs = await db.workspace_members.find(
                {"user_id": user["user_id"]}, {"_id": 0, "workspace_id": 1}
            ).to_list(100)
            member_ws_ids = [m["workspace_id"] for m in member_docs]
            ownership_filter = {"$or": [
                {"owner_id": user["user_id"]},
                {"workspace_id": {"$in": member_ws_ids}} if member_ws_ids else {"_id": None},
            ]}
        
        filters = [{"disabled": {"$ne": True}}] if not include_disabled else []
        filters.append({"is_deleted": {"$ne": True}})
        if ownership_filter:
            filters.append(ownership_filter)

        # Server-side typeahead search
        if search and search.strip():
            from nexus_utils import safe_regex
            search_regex = {"$regex": safe_regex(search), "$options": "i"}
            filters.append({"$or": [{"name": search_regex}, {"description": search_regex}]})

        query = {"$and": filters} if filters else {}
        workspaces = await db.workspaces.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
        
        if workspaces:
            ws_ids = [ws["workspace_id"] for ws in workspaces]
            # Batch: get all channels for all workspaces at once
            all_channels = await db.channels.find(
                {"workspace_id": {"$in": ws_ids}}, {"workspace_id": 1, "ai_agents": 1, "_id": 0}
            ).to_list(500)
            # Batch: count nexus agents per workspace
            nexus_pipeline = [
                {"$match": {"workspace_id": {"$in": ws_ids}}},
                {"$group": {"_id": "$workspace_id", "count": {"$sum": 1}}}
            ]
            nexus_counts = {doc["_id"]: doc["count"] async for doc in db.nexus_agents.aggregate(nexus_pipeline)}
            # Build per-workspace agent sets
            ws_agents = {}
            for ch in all_channels:
                wsid = ch["workspace_id"]
                ws_agents.setdefault(wsid, set()).update(ch.get("ai_agents") or [])
            for ws in workspaces:
                wsid = ws["workspace_id"]
                unique = ws_agents.get(wsid, set())
                nxa = nexus_counts.get(wsid, 0)
                ws["agent_count"] = len(unique)
                ws["nexus_agent_count"] = nxa
                ws["total_agents"] = len(unique) + nxa
            
            # Batch: check persist status for all workspaces
            persist_channels = await db.channels.find(
                {"workspace_id": {"$in": ws_ids}, "auto_collab_persist": True},
                {"_id": 0, "workspace_id": 1, "channel_id": 1, "name": 1, "disabled_agents": 1, "ai_agents": 1}
            ).to_list(100)
            
            ws_persist = {}
            for ch in persist_channels:
                wsid = ch["workspace_id"]
                if wsid not in ws_persist:
                    ws_persist[wsid] = []
                # Check session health — DB is the source of truth, in-memory is supplementary
                from collaboration_engine import persist_sessions
                session = persist_sessions.get(ch["channel_id"], {})
                disabled = ch.get("disabled_agents") or []
                total = len(ch.get("ai_agents") or [])
                failed = len(disabled)
                
                # If DB says persist is on, it's at minimum active
                status = "active"  # green — DB flag is true
                if total > 0 and failed > 0 and failed < (total / 2):
                    status = "warning"  # yellow — some agents disabled
                if total > 0 and failed >= (total / 2):
                    status = "error"  # red — majority agents failed
                # In-memory session can override to warning if errors detected
                if session.get("consecutive_errors", 0) > 3:
                    status = "warning"
                
                ws_persist[wsid].append({"channel": ch.get("name", ""), "channel_id": ch["channel_id"], "status": status})
            
            for ws in workspaces:
                wsid = ws["workspace_id"]
                persist_info = ws_persist.get(wsid, [])
                ws["persist_channels"] = persist_info
                if any(p["status"] == "active" for p in persist_info):
                    ws["persist_status"] = "active"
                elif any(p["status"] == "warning" for p in persist_info):
                    ws["persist_status"] = "warning"
                elif persist_info:
                    ws["persist_status"] = "error"
                else:
                    ws["persist_status"] = "none"
        
        return workspaces
    
    @api_router.post("/workspaces")
    async def create_workspace(data: WorkspaceCreate, request: Request):
        user = await get_current_user(request)
        workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
        kg_enabled = getattr(data, "kg_enabled", False)
        workspace = {
            "workspace_id": workspace_id,
            "name": data.name,
            "description": data.description,
            "owner_id": user["user_id"],
            "members": [user["user_id"]],
            "disabled": False,
            "tpm_agent_id": None,
            "knowledge_graph": {
                "enabled": kg_enabled,
                "share_with_org": getattr(data, "kg_share_with_org", True),
                "consented_by": user["user_id"] if kg_enabled else None,
                "consented_at": datetime.now(timezone.utc).isoformat() if kg_enabled else None,
                "consent_version": "1.0",
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        try:
            await db.workspaces.insert_one(workspace)
        except Exception as e:
            logger.error(f"Failed to insert workspace: {e}")
            raise HTTPException(500, f"Database error creating workspace: {str(e)}")
        
        # Auto-create default TPM channel
        try:
            tpm_channel_id = f"ch_{uuid.uuid4().hex[:12]}"
            tpm_channel = {
                "channel_id": tpm_channel_id,
                "workspace_id": workspace_id,
                "name": "tpm-coordination",
                "description": "TPM coordination channel — task assignments, status updates, and agent orchestration. Designate a TPM agent in Workspace Settings.",
                "ai_agents": [],
                "disabled_agents": [],
                "is_tpm_channel": True,
                "auto_collab_enabled": False,
                "pinned": True,
                "order_index": 0,
                "created_by": user["user_id"],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.channels.insert_one(tpm_channel)
        except Exception as e:
            logger.warning(f"Failed to create TPM channel for {workspace_id}: {e}")
        
        result = await db.workspaces.find_one(
            {"workspace_id": workspace_id}, {"_id": 0}
        )
        if not result:
            raise HTTPException(500, "Workspace created but could not be retrieved")
        return result
    
    @api_router.get("/workspaces/{workspace_id}")
    async def get_workspace(workspace_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        workspace = await db.workspaces.find_one(
            {"workspace_id": workspace_id}, {"_id": 0}
        )
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        return workspace

    @api_router.get("/workspaces/{workspace_id}/ai-key-health")
    async def get_workspace_ai_key_health(workspace_id: str, request: Request, channel_id: Optional[str] = None):
        user = await get_current_user(request)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        return await _resolve_workspace_agent_health(user, workspace, channel_id)
    
    @api_router.put("/workspaces/{workspace_id}")
    async def update_workspace(workspace_id: str, data: WorkspaceUpdate, request: Request):
        """Update workspace name or description"""
        user = await get_current_user(request)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        if workspace["owner_id"] != user["user_id"]:
            raise HTTPException(403, "Only the workspace owner can update it")
        
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.name is not None and data.name.strip():
            updates["name"] = data.name.strip()
        if data.description is not None:
            updates["description"] = data.description.strip()
        
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": updates}
        )
        
        updated = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        return updated
    
    @api_router.put("/workspaces/{workspace_id}/disable")
    async def disable_workspace(workspace_id: str, request: Request):
        """Disable or enable a workspace"""
        user = await get_current_user(request)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        if workspace["owner_id"] != user["user_id"]:
            raise HTTPException(403, "Only the workspace owner can disable it")
        
        # Toggle disabled status
        new_status = not workspace.get("disabled", False)
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"disabled": new_status, "disabled_at": datetime.now(timezone.utc).isoformat() if new_status else None}}
        )
        
        updated = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        return updated
    
    # Single and bulk workspace deletion handled by routes_workspace_deletion.py
    
    
    AGENT_MODELS = {
        "claude": [
            {"id": "claude-opus-4-20250514", "name": "Claude Opus 4.6"},
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4.6", "default": True},
            {"id": "claude-opus-4-5-20250414", "name": "Claude Opus 4.5"},
            {"id": "claude-sonnet-4-5-20250414", "name": "Claude Sonnet 4.5"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku (fast)"},
        ],
        "chatgpt": [
            {"id": "gpt-5.4", "name": "GPT-5.4", "default": True},
            {"id": "gpt-5.4-mini", "name": "GPT-5.4 Mini"},
            {"id": "gpt-5.4-nano", "name": "GPT-5.4 Nano"},
            {"id": "gpt-5.2", "name": "GPT-5.2"},
            {"id": "gpt-5", "name": "GPT-5"},
            {"id": "gpt-4.1", "name": "GPT-4.1"},
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (fast)"},
            {"id": "o3", "name": "o3 (reasoning)"},
            {"id": "o3-pro", "name": "o3-pro (reasoning)"},
            {"id": "o3-mini", "name": "o3-mini (fast reasoning)"},
        ],
        "gemini": [
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "default": True},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (fast)"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "default": True},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
        ],
        "grok": [
            {"id": "grok-3", "name": "Grok 3", "default": True},
            {"id": "grok-3-mini", "name": "Grok 3 Mini (fast)"},
        ],
        "perplexity": [
            {"id": "sonar-pro", "name": "Sonar Pro", "default": True},
            {"id": "sonar", "name": "Sonar (fast)"},
        ],
        "mistral": [
            {"id": "mistral-large-latest", "name": "Mistral Large", "default": True},
            {"id": "mistral-medium-latest", "name": "Mistral Medium"},
            {"id": "mistral-small-latest", "name": "Mistral Small (fast)"},
        ],
        "cohere": [
            {"id": "command-a-03-2025", "name": "Command A", "default": True},
            {"id": "command-a-03-2025", "name": "Command A (Latest)", "default": True},
        ],
        "groq": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "default": True},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B (fast)"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B"},
        ],
        "mercury": [
            {"id": "mercury-2", "name": "Mercury 2", "default": True},
        ],
        "pi": [
            {"id": "inflection/inflection-3-pi", "name": "Pi (Inflection 3)", "default": True},
        ],
        "manus": [
            {"id": "manus-1", "name": "Manus 1", "default": True},
        ],
        "qwen": [
            {"id": "qwen-plus", "name": "Qwen Plus", "default": True},
            {"id": "qwen-max", "name": "Qwen Max"},
            {"id": "qwen-turbo", "name": "Qwen Turbo (fast)"},
        ],
        "kimi": [
            {"id": "kimi-k2.5", "name": "Kimi K2.5", "default": True},
            {"id": "moonshot-v1-128k", "name": "Moonshot v1 128K"},
        ],
        "llama": [
            {"id": "meta-llama/Llama-4-Scout-17B-16E-Instruct", "name": "Llama 4 Scout", "default": True},
            {"id": "meta-llama/Llama-4-Maverick-17B-128E-Instruct", "name": "Llama 4 Maverick"},
            {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B"},
        ],
        "glm": [
            {"id": "glm-4-plus", "name": "GLM-4 Plus", "default": True},
            {"id": "glm-4", "name": "GLM-4"},
        ],
        "cursor": [
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4 (Cursor)", "default": True},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (Cursor)"},
        ],
        "notebooklm": [
            {"id": "google/gemini-2.5-pro-preview", "name": "Gemini 2.5 Pro (NotebookLM)", "default": True},
            {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash (NotebookLM)"},
        ],
        "copilot": [
            {"id": "openai/gpt-4o", "name": "GPT-4o (Copilot)", "default": True},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini (Copilot)"},
        ],
    }
    
    @api_router.get("/ai-models")
    async def get_available_models(request: Request):
        """Get available models per agent for channel configuration"""
        await get_current_user(request)
        return {"models": AGENT_MODELS}
    
    
    @api_router.get("/workspaces/{workspace_id}/settings")
    async def get_workspace_settings(workspace_id: str, request: Request):
        """Get workspace-level settings (tenant config)"""
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        settings = await db.workspace_settings.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not settings:
            settings = {"workspace_id": workspace_id, "auto_collab_max_rounds": 10}
        return settings
    
    @api_router.put("/workspaces/{workspace_id}/settings")
    async def update_workspace_settings(workspace_id: str, request: Request):
        """Update workspace-level settings (admin only)"""
        user = await get_current_user(request)
        # Verify user is workspace owner or admin
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        if workspace.get("owner_id") != user["user_id"]:
            # Check if super admin
            from routes_admin import is_super_admin
            if not await is_super_admin(db, user["user_id"]):
                raise HTTPException(403, "Only workspace owner or admin can change settings")
        
        body = await request.json()
        updates = {"workspace_id": workspace_id}
        
        if "auto_collab_max_rounds" in body:
            val = int(body["auto_collab_max_rounds"])
            updates["auto_collab_max_rounds"] = min(max(val, 5), 50)
        if "theme" in body:
            updates["theme"] = body["theme"]
        if "branding" in body:
            updates["branding"] = body["branding"]
        
        await db.workspace_settings.update_one(
            {"workspace_id": workspace_id},
            {"$set": updates},
            upsert=True,
        )
        
        result = await db.workspace_settings.find_one({"workspace_id": workspace_id}, {"_id": 0})
        return result
    

    # ============ TPM Designation ============

    @api_router.get("/workspaces/{workspace_id}/tpm")
    async def get_tpm(workspace_id: str, request: Request):
        """Get the designated TPM agent for this workspace."""
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "tpm_agent_id": 1})
        tpm_id = (ws or {}).get("tpm_agent_id")
        tpm_agent = None
        if tpm_id:
            tpm_agent = await db.nexus_agents.find_one({"agent_id": tpm_id}, {"_id": 0})
        # Get TPM channel
        tpm_channel = await db.channels.find_one(
            {"workspace_id": workspace_id, "is_tpm_channel": True}, {"_id": 0})
        return {
            "tpm_agent_id": tpm_id,
            "tpm_agent": tpm_agent,
            "tpm_channel": tpm_channel,
        }

    @api_router.put("/workspaces/{workspace_id}/tpm")
    async def set_tpm(workspace_id: str, request: Request):
        """Designate an agent as the TPM for this workspace. Only one TPM allowed."""
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        body = await request.json()
        agent_id = body.get("agent_id")
        
        if agent_id:
            # Verify agent exists in this workspace
            agent = await db.nexus_agents.find_one(
                {"agent_id": agent_id, "workspace_id": workspace_id}, {"_id": 0})
            if not agent:
                raise HTTPException(404, "Agent not found in this workspace")
            
            # Check if another agent is already TPM
            ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "tpm_agent_id": 1})
            old_tpm = (ws or {}).get("tpm_agent_id")
            if old_tpm and old_tpm != agent_id:
                # Remove old TPM from the TPM channel
                await db.channels.update_one(
                    {"workspace_id": workspace_id, "is_tpm_channel": True},
                    {"$pull": {"ai_agents": old_tpm}}
                )
            
            # Set the new TPM
            await db.workspaces.update_one(
                {"workspace_id": workspace_id},
                {"$set": {"tpm_agent_id": agent_id}}
            )
            
            # Mark agent as TPM category
            await db.nexus_agents.update_one(
                {"agent_id": agent_id},
                {"$set": {"category": "tpm", "preferred_role": "tpm"}}
            )
            
            # Add TPM agent to the TPM channel (create channel if missing)
            tpm_channel = await db.channels.find_one(
                {"workspace_id": workspace_id, "is_tpm_channel": True})
            if tpm_channel:
                await db.channels.update_one(
                    {"channel_id": tpm_channel["channel_id"]},
                    {"$set": {"ai_agents": [agent_id]}}
                )
            else:
                # Create TPM channel if it doesn't exist
                ch_id = f"ch_{uuid.uuid4().hex[:12]}"
                await db.channels.insert_one({
                    "channel_id": ch_id,
                    "workspace_id": workspace_id,
                    "name": "tpm-coordination",
                    "description": f"TPM coordination channel managed by {agent.get('name', agent_id)}",
                    "ai_agents": [agent_id],
                    "disabled_agents": [],
                    "is_tpm_channel": True,
                    "auto_collab_enabled": True,
                    "pinned": True,
                    "order_index": 0,
                    "created_by": user["user_id"],
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            
            # If old TPM was set to category=tpm, reset it
            if old_tpm and old_tpm != agent_id:
                await db.nexus_agents.update_one(
                    {"agent_id": old_tpm},
                    {"$set": {"category": "general", "preferred_role": None}}
                )
            
            return {"message": f"TPM set to {agent.get('name', agent_id)}", "tpm_agent_id": agent_id}
        else:
            # Remove TPM designation
            ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "tpm_agent_id": 1})
            old_tpm = (ws or {}).get("tpm_agent_id")
            await db.workspaces.update_one(
                {"workspace_id": workspace_id},
                {"$set": {"tpm_agent_id": None}}
            )
            if old_tpm:
                await db.nexus_agents.update_one(
                    {"agent_id": old_tpm},
                    {"$set": {"category": "general", "preferred_role": None}}
                )
                await db.channels.update_one(
                    {"workspace_id": workspace_id, "is_tpm_channel": True},
                    {"$set": {"ai_agents": []}}
                )
            return {"message": "TPM designation removed", "tpm_agent_id": None}


