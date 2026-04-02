"""Nexus Helper Agent — Embedded AI assistant for platform guidance."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from nexus_utils import now_iso
from nexus_config import FEATURE_FLAGS

logger = logging.getLogger(__name__)

PAGE_GROUPS = {
    "core": {
        "tabs": ["dashboard", "members", "drive", "schedules", "tpm"],
        "desc": "Workspace home, team members, file storage, and scheduling",
        "caps": ["create channels", "manage members", "upload files", "view dashboard stats", "schedule agent runs"],
        "tips": ["Use Ctrl+K for quick navigation", "Pin frequently used tabs to the sidebar"],
    },
    "chat": {
        "tabs": ["chat"],
        "desc": "AI collaboration chat with 19 model providers",
        "caps": ["send messages", "mention agents with @", "trigger multi-agent collaboration", "upload files", "search messages", "share conversations"],
        "tips": ["Type @ to mention a specific AI model", "Use Ctrl+Enter to send", "Click the brain icon for auto-collaboration"],
    },
    "project_mgmt": {
        "tabs": ["projects", "tasks", "gantt", "planner", "ideation"],
        "desc": "Project management with tasks, Gantt charts, calendar planning, and brainstorming",
        "caps": ["create projects", "manage tasks", "set milestones", "view Gantt timeline", "calendar planning", "brainstorm with AI"],
        "tips": ["Link projects to chat channels for AI-assisted project management"],
    },
    "agent_builder": {
        "tabs": ["agents", "studio", "skill-matrix", "catalog", "training", "skills", "playground", "evaluation", "fine-tuning"],
        "desc": "Custom AI agent builder with skills, training, evaluation, and prompt optimization",
        "caps": ["create custom agents", "configure skills", "train with documents and URLs", "run evaluations", "test in playground", "optimize prompts"],
        "tips": ["Train agents with your docs for domain-specific responses", "Use the playground to test before deploying"],
    },
    "orchestration": {
        "tabs": ["orchestration", "a2a-pipelines", "operator", "orch-schedules", "collab-templates", "arena", "benchmarks", "benchmark-compare", "deployments"],
        "desc": "Multi-agent orchestration, A2A pipelines, arena battles, benchmarks, and deployments",
        "caps": ["create orchestrations", "build A2A pipelines", "run arena battles", "benchmark agents", "deploy autonomous agents"],
        "tips": ["Arena lets you compare models side-by-side on the same prompt", "Benchmark before deploying to production"],
    },
    "build_code": {
        "tabs": ["code", "docs", "knowledge", "artifacts", "webhooks", "directives", "workflows"],
        "desc": "Code repository, documentation, knowledge base, artifacts, and automation",
        "caps": ["view and edit code", "manage documentation", "build knowledge base", "create artifacts", "configure webhooks", "set up automation workflows"],
        "tips": ["AI agents can write directly to the code repo during collaboration"],
    },
    "media": {
        "tabs": ["images", "video", "audio", "media"],
        "desc": "AI image generation, video concepts, text-to-speech, and media library",
        "caps": ["generate images", "create video concepts", "text-to-speech", "speech-to-text", "manage media library"],
        "tips": ["SFX generation uses ElevenLabs — requires ELEVENLABS_API_KEY"],
    },
    "optimization": {
        "tabs": ["optimization", "compression-profiles", "compression-runs", "compression-compare"],
        "desc": "NAVC — Nexus Adaptive Vector Compression for inference and retrieval efficiency",
        "caps": ["create compression profiles", "run benchmarks", "compare results", "promote profiles to production"],
        "tips": ["Start with a 4-bit vector index profile for knowledge base compression"],
    },
    "insights": {
        "tabs": ["analytics", "reports", "cost-dashboard", "cost-alerts", "roi", "roi-comparison", "leaderboard", "performance", "review-analytics", "strategic", "data-export"],
        "desc": "Analytics, cost tracking, ROI analysis, and performance dashboards",
        "caps": ["view analytics", "monitor costs", "set budget alerts", "export data", "compare ROI across workspaces"],
        "tips": ["Set up cost alerts to avoid unexpected AI spend"],
    },
    "security": {
        "tabs": ["security", "audit", "mfa", "sso", "scim"],
        "desc": "Security settings, audit logs, MFA, SSO, and SCIM provisioning",
        "caps": ["view audit logs", "manage MFA", "configure SSO", "SCIM user provisioning"],
        "tips": ["Enable MFA for all admin accounts"],
    },
    "settings": {
        "tabs": ["settings"],
        "desc": "AI provider keys, profile settings, and preferences",
        "caps": ["configure API keys", "manage AI providers", "update profile"],
        "tips": ["You need at least one AI provider key to use AI features"],
    },
    "admin": {
        "tabs": ["admin"],
        "desc": "Platform administration (super_admin only)",
        "caps": ["manage all users", "configure platform keys", "view system health", "review bugs", "audit logs"],
        "tips": ["Use system health to monitor provider uptime"],
    },
}

TAB_TO_GROUP = {}
for group_key, group in PAGE_GROUPS.items():
    for tab in group["tabs"]:
        TAB_TO_GROUP[tab] = group_key


def _get_page_context(tab: str) -> dict:
    group_key = TAB_TO_GROUP.get(tab, "core")
    return PAGE_GROUPS.get(group_key, PAGE_GROUPS["core"])


RATE_LIMIT_PER_HOUR = 30


class HelperMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    page_context: str = Field(default="dashboard")
    workspace_id: Optional[str] = None
    error_context: Optional[str] = None


def register_helper_routes(api_router, db, get_current_user):
    def _check_flag():
        if not FEATURE_FLAGS.get("nexus_helper", {}).get("enabled", True):
            raise HTTPException(501, FEATURE_FLAGS.get("nexus_helper", {}).get("reason", "Helper not enabled"))

    async def _check_rate_limit(user_id: str):
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        conv = await db.helper_conversations.find_one(
            {"user_id": user_id}, {"_id": 0, "messages": 1})
        if not conv:
            return
        recent = [m for m in (conv.get("messages") or [])
                  if m.get("role") == "user" and m.get("ts", "") > one_hour_ago]
        if len(recent) >= RATE_LIMIT_PER_HOUR:
            raise HTTPException(429, f"Helper rate limit reached ({RATE_LIMIT_PER_HOUR}/hour). Try again shortly.")

    def _build_system_prompt(user, tab, workspace=None, permissions=None):
        ctx = _get_page_context(tab)
        role = user.get("platform_role", "user")
        name = user.get("name", "there")
        prompt = (
            f"You are Nexus Helper, an AI assistant embedded in the Nexus Cloud platform.\n"
            f"You are helping {name} (role: {role}) who is viewing: {tab}\n\n"
            f"CURRENT SECTION: {ctx['desc']}\n"
            f"AVAILABLE ACTIONS: {', '.join(ctx['caps'])}\n\n"
            "RULES:\n"
            "- Help users understand and use Nexus features.\n"
            "- You may propose and execute platform actions on the user's behalf.\n"
            "- For read-only queries, respond directly with information.\n"
            "- For write/mutating actions, propose an action card that the user must approve before execution.\n"
            "- When proposing an action, include a JSON block with this format:\n"
            '  ```action\n  {"title": "...", "summary": "...", "tool_calls": [{"tool": "tool_name", "params": {...}}]}\n  ```\n'
            "- Available tools: create_project, create_task, repo_write_file, repo_read_file, repo_list_files, "
            "wiki_create_page, wiki_read_page, memory_add, memory_search, execute_code, create_artifact, "
            "search_messages, list_channels, list_projects.\n"
            "- Keep answers concise and actionable.\n"
            "- If the user asks about a feature they cannot access, explain what permission or plan is needed.\n"
            "- Never make up feature capabilities. Only describe what Nexus actually has.\n"
            "- You cannot see the user's screen.\n"
        )
        if workspace:
            mods = ", ".join(workspace.get("enabled_modules", ["core"]))
            prompt += f"\nWORKSPACE: {workspace.get('name', '')} | MODULES: {mods}\n"
        if permissions:
            prompt += f"USER PERMISSIONS: {', '.join(permissions)}\n"
        if role == "super_admin":
            prompt += "This user is a super_admin with full platform access.\n"
        elif role == "observer":
            prompt += "This user has Observer (read-only) access.\n"
        return prompt

    @api_router.post("/helper/chat")
    async def helper_chat(data: HelperMessage, request: Request):
        _check_flag()
        user = await get_current_user(request)
        user_id = user["user_id"]
        await _check_rate_limit(user_id)

        workspace = None
        permissions = None
        ws_id = data.workspace_id or ""
        if ws_id:
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, ws_id)
            workspace = await db.workspaces.find_one(
                {"workspace_id": ws_id},
                {"_id": 0, "name": 1, "workspace_id": 1, "enabled_modules": 1, "owner_id": 1})
            try:
                from routes.routes_rbac import PERMISSIONS, has_permission
                member = await db.workspace_members.find_one(
                    {"workspace_id": ws_id, "user_id": user_id}, {"_id": 0, "role": 1})
                user_role = (member or {}).get("role", "user")
                if workspace and workspace.get("owner_id") == user_id:
                    user_role = "admin"
                permissions = [p for p in PERMISSIONS if has_permission(user_role, p)]
            except Exception:
                permissions = None

        system_prompt = _build_system_prompt(user, data.page_context, workspace, permissions)

        # Assemble conversation history for multi-turn
        conv = await db.helper_conversations.find_one(
            {"user_id": user_id}, {"_id": 0, "messages": 1})
        history_msgs = (conv.get("messages") or [])[-10:] if conv else []
        user_message = ""
        for msg in history_msgs:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            user_message += f"{prefix}: {msg['content']}\n"
        user_message += f"User: {data.message}"
        if data.error_context:
            user_message += f"\n[Error on screen: {data.error_context}]"
        user_message += "\nAssistant:"

        # Key resolution: Claude > ChatGPT > Gemini
        from collaboration_core import get_ai_key_for_agent
        agent_key = "claude"
        api_key, key_source = await get_ai_key_for_agent(user_id, ws_id, "claude")
        if not api_key:
            agent_key = "chatgpt"
            api_key, key_source = await get_ai_key_for_agent(user_id, ws_id, "chatgpt")
        if not api_key:
            agent_key = "gemini"
            api_key, key_source = await get_ai_key_for_agent(user_id, ws_id, "gemini")
        if not api_key:
            raise HTTPException(503, "No AI provider key configured. Go to Settings > AI Keys to add one.")

        # Budget pre-check
        try:
            from managed_keys import check_usage_budget
            org_id = (workspace or {}).get("org_id")
            budget = await check_usage_budget(agent_key, 0.003, workspace_id=ws_id, org_id=org_id, user_id=user_id)
            if budget.get("blocked"):
                raise HTTPException(429, "AI budget reached. Check cost alerts or contact your admin.")
        except HTTPException:
            raise
        except Exception as _be:
            logger.warning(f"Helper budget check skipped: {_be}")

        # Call AI
        try:
            from ai_providers import call_ai_direct
            response = await call_ai_direct(agent_key, api_key, system_prompt, user_message, workspace_id=ws_id, db=db)
        except Exception as e:
            logger.error(f"Helper agent error: {e}")
            raise HTTPException(502, f"Helper unavailable: {str(e)[:200]}")

        # Record usage
        try:
            from managed_keys import record_usage_event
            await record_usage_event(agent_key, 0.003, user_id=user_id, workspace_id=ws_id,
                usage_type="helper", key_source=key_source, call_count=1,
                metadata={"page": data.page_context, "agent": agent_key})
        except Exception as _e:
            import logging; logging.getLogger("routes/routes_helper").warning(f"Suppressed: {_e}")

        # Store conversation (capped at 20 messages)
        now = now_iso()
        await db.helper_conversations.update_one(
            {"user_id": user_id},
            {"$push": {"messages": {"$each": [
                {"role": "user", "content": data.message, "page": data.page_context, "ts": now},
                {"role": "assistant", "content": response, "agent": agent_key, "ts": now},
            ], "$slice": -20}}, "$set": {"updated_at": now}},
            upsert=True)

        # Parse action proposals from AI response
        actions = []
        import re as _re
        action_blocks = _re.findall(r'```action\s*\n(.*?)\n```', response, _re.DOTALL)
        for block in action_blocks:
            try:
                import json as _json
                action_data = _json.loads(block)
                from helper_actions import build_helper_action
                action = await build_helper_action(db, user_id, ws_id, action_data)
                actions.append(action)
            except Exception as ae:
                logger.warning(f"Failed to parse action block: {ae}")

        # Strip action blocks from display text
        clean_response = _re.sub(r'```action\s*\n.*?\n```', '', response, flags=_re.DOTALL).strip()

        return {"response": clean_response, "agent": agent_key, "page_context": data.page_context, "actions": actions}

    # ============ Action Control Endpoints ============

    @api_router.post("/helper/actions/{action_id}/approve")
    async def approve_action(action_id: str, request: Request):
        _check_flag()
        user = await get_current_user(request)
        action = await db.helper_actions.find_one({"action_id": action_id, "user_id": user["user_id"]}, {"_id": 0})
        if not action:
            raise HTTPException(404, "Action not found")
        if action["status"] not in ("pending_review",):
            raise HTTPException(400, f"Action is {action['status']}, cannot approve")
        # RBAC check
        ws_id = action.get("workspace_id", "")
        if ws_id:
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, ws_id)
        await db.helper_actions.update_one(
            {"action_id": action_id}, {"$set": {"status": "approved", "approved_by": user["user_id"], "approved_at": now_iso()}})
        from helper_actions import execute_helper_action, audit_helper_action
        await audit_helper_action(db, action_id, user["user_id"], ws_id, "approved")
        result = await execute_helper_action(db, action_id, user, ws_id)
        return result

    @api_router.post("/helper/actions/{action_id}/edit-and-approve")
    async def edit_and_approve_action(action_id: str, request: Request):
        _check_flag()
        user = await get_current_user(request)
        body = await request.json()
        action = await db.helper_actions.find_one({"action_id": action_id, "user_id": user["user_id"]}, {"_id": 0})
        if not action:
            raise HTTPException(404, "Action not found")
        if action["status"] != "pending_review":
            raise HTTPException(400, "Can only edit pending actions")
        updates = {}
        if "tool_calls" in body:
            from helper_actions import validate_tool_calls, classify_risk, resolve_permissions
            errors = validate_tool_calls(body["tool_calls"])
            if errors:
                raise HTTPException(400, f"Invalid tool calls: {'; '.join(errors)}")
            updates["tool_calls"] = body["tool_calls"]
            updates["risk_level"] = classify_risk(body["tool_calls"])
            updates["required_permissions"] = resolve_permissions(body["tool_calls"])
        if "title" in body:
            updates["title"] = body["title"]
        if "summary" in body:
            updates["summary"] = body["summary"]
        updates["status"] = "approved"
        updates["approved_by"] = user["user_id"]
        updates["approved_at"] = now_iso()
        updates["updated_at"] = now_iso()
        await db.helper_actions.update_one({"action_id": action_id}, {"$set": updates})
        ws_id = action.get("workspace_id", "")
        from helper_actions import execute_helper_action, audit_helper_action
        await audit_helper_action(db, action_id, user["user_id"], ws_id, "edited_and_approved")
        return await execute_helper_action(db, action_id, user, ws_id)

    @api_router.post("/helper/actions/{action_id}/dismiss")
    async def dismiss_action(action_id: str, request: Request):
        _check_flag()
        user = await get_current_user(request)
        result = await db.helper_actions.update_one(
            {"action_id": action_id, "user_id": user["user_id"], "status": "pending_review"},
            {"$set": {"status": "dismissed", "dismissed_by": user["user_id"], "dismissed_at": now_iso()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Action not found or not pending")
        from helper_actions import audit_helper_action
        await audit_helper_action(db, action_id, user["user_id"], "", "dismissed")
        return {"status": "dismissed"}

    @api_router.get("/helper/actions")
    async def list_actions(request: Request, limit: int = 20):
        _check_flag()
        user = await get_current_user(request)
        actions = await db.helper_actions.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"actions": actions}

    @api_router.get("/helper/actions/{action_id}")
    async def get_action(action_id: str, request: Request):
        _check_flag()
        user = await get_current_user(request)
        action = await db.helper_actions.find_one(
            {"action_id": action_id, "user_id": user["user_id"]}, {"_id": 0})
        if not action:
            raise HTTPException(404, "Action not found")
        return action

    @api_router.get("/helper/context")
    async def helper_context(request: Request, page: str = "dashboard", workspace_id: str = ""):
        _check_flag()
        user = await get_current_user(request)
        ctx = _get_page_context(page)
        result = {"page": page, "description": ctx["desc"], "tips": ctx.get("tips", []), "capabilities": ctx.get("caps", [])}
        suggestions = []
        if page == "dashboard":
            if await db.workspaces.count_documents({"owner_id": user["user_id"]}) == 0:
                suggestions.append("Create your first workspace to start using Nexus")
        elif page == "chat" and workspace_id:
            if await db.channels.count_documents({"workspace_id": workspace_id}) == 0:
                suggestions.append("Create a channel and add AI agents to start collaborating")
        elif page == "settings":
            from key_resolver import get_integration_key
            has_key = bool(await get_integration_key(db, "OPENAI_API_KEY") or await get_integration_key(db, "ANTHROPIC_API_KEY"))
            if not has_key:
                suggestions.append("Add an AI provider key to enable AI collaboration")
        result["suggestions"] = suggestions
        return result

    @api_router.get("/helper/history")
    async def helper_history(request: Request):
        _check_flag()
        user = await get_current_user(request)
        conv = await db.helper_conversations.find_one({"user_id": user["user_id"]}, {"_id": 0, "messages": 1})
        return {"messages": (conv or {}).get("messages", [])}

    @api_router.delete("/helper/history")
    async def clear_helper_history(request: Request):
        _check_flag()
        user = await get_current_user(request)
        await db.helper_conversations.delete_one({"user_id": user["user_id"]})
        return {"status": "cleared"}
