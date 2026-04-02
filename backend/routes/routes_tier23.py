"""Tier 2+3 — Enhanced Agent Builder, AI Team Roles, Real-Time Collab, Multilingual, Voice, Workflow Templates"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)

# AI Team Roles
AVAILABLE_ROLES = [
    {"key": "strategist", "name": "Strategist", "prompt_prefix": "You are a strategic thinker. Focus on big-picture analysis, competitive positioning, and long-term planning."},
    {"key": "coder", "name": "Coder", "prompt_prefix": "You are a software engineer. Focus on writing clean, efficient, well-tested code with clear documentation."},
    {"key": "researcher", "name": "Researcher", "prompt_prefix": "You are a thorough researcher. Focus on finding reliable sources, cross-referencing data, and providing citations."},
    {"key": "critic", "name": "Critic", "prompt_prefix": "You are a constructive critic. Challenge assumptions, identify weaknesses, and suggest improvements."},
    {"key": "writer", "name": "Writer", "prompt_prefix": "You are a skilled writer. Focus on clear, engaging, well-structured prose that communicates effectively."},
    {"key": "designer", "name": "Designer", "prompt_prefix": "You are a UX/UI designer. Focus on user experience, visual hierarchy, accessibility, and design systems."},
    {"key": "analyst", "name": "Analyst", "prompt_prefix": "You are a data analyst. Focus on quantitative analysis, metrics, trends, and data-driven recommendations."},
    {"key": "qa", "name": "QA Engineer", "prompt_prefix": "You are a QA engineer. Focus on finding edge cases, writing test scenarios, and ensuring quality."},
]

# Extended Workflow Templates
EXTENDED_TEMPLATES = [
    {"template_id": "wst_competitive_analysis", "name": "Competitive Analysis", "description": "Research competitors, analyze strengths/weaknesses, produce strategic report", "category": "research", "nodes": [{"type": "input", "label": "Competitor Names"}, {"type": "ai_agent", "label": "Market Research", "ai_model": "perplexity"}, {"type": "ai_agent", "label": "SWOT Analysis", "ai_model": "claude"}, {"type": "ai_agent", "label": "Strategic Recommendations", "ai_model": "chatgpt"}, {"type": "merge", "label": "Compile Report"}, {"type": "output", "label": "Analysis Report"}]},
    {"template_id": "wst_pitch_deck_creator", "name": "Pitch Deck Creator", "description": "Create a complete pitch deck from a business description", "category": "content", "nodes": [{"type": "input", "label": "Business Description"}, {"type": "ai_agent", "label": "Narrative Structure", "ai_model": "claude"}, {"type": "ai_agent", "label": "Market Data", "ai_model": "perplexity"}, {"type": "ai_agent", "label": "Visual Design Notes", "ai_model": "gemini"}, {"type": "merge", "label": "Combine"}, {"type": "output", "label": "Pitch Deck"}]},
    {"template_id": "wst_blog_generator", "name": "Blog Post Generator", "description": "Research topic, outline, draft, edit, and SEO optimize a blog post", "category": "content", "nodes": [{"type": "input", "label": "Topic"}, {"type": "ai_agent", "label": "Research", "ai_model": "perplexity"}, {"type": "ai_agent", "label": "Draft", "ai_model": "chatgpt"}, {"type": "ai_agent", "label": "Edit & Polish", "ai_model": "claude"}, {"type": "output", "label": "Blog Post"}]},
    {"template_id": "wst_meeting_notes", "name": "Meeting Notes Processor", "description": "Transcribe, summarize, extract action items from meeting audio/text", "category": "productivity", "nodes": [{"type": "input", "label": "Meeting Notes/Audio"}, {"type": "ai_agent", "label": "Summarize", "ai_model": "chatgpt"}, {"type": "ai_agent", "label": "Extract Actions", "ai_model": "claude"}, {"type": "output", "label": "Summary + Actions"}]},
    {"template_id": "wst_market_research", "name": "Market Research Report", "description": "Deep market analysis with TAM/SAM/SOM, trends, and competitive landscape", "category": "research", "nodes": [{"type": "input", "label": "Market/Industry"}, {"type": "ai_agent", "label": "Market Sizing", "ai_model": "perplexity"}, {"type": "ai_agent", "label": "Trend Analysis", "ai_model": "gemini"}, {"type": "ai_agent", "label": "Competitive Map", "ai_model": "claude"}, {"type": "merge", "label": "Compile"}, {"type": "output", "label": "Market Report"}]},
    {"template_id": "wst_social_media", "name": "Social Media Campaign", "description": "Generate social media content across platforms from a campaign brief", "category": "marketing", "nodes": [{"type": "input", "label": "Campaign Brief"}, {"type": "ai_agent", "label": "Twitter/X Posts", "ai_model": "chatgpt"}, {"type": "ai_agent", "label": "LinkedIn Posts", "ai_model": "claude"}, {"type": "ai_agent", "label": "Visual Concepts", "ai_model": "gemini"}, {"type": "merge", "label": "Campaign Package"}, {"type": "output", "label": "Social Content"}]},
    {"template_id": "wst_feedback_analyzer", "name": "Customer Feedback Analyzer", "description": "Analyze customer feedback, categorize themes, prioritize improvements", "category": "product", "nodes": [{"type": "input", "label": "Feedback Data"}, {"type": "ai_agent", "label": "Sentiment Analysis", "ai_model": "chatgpt"}, {"type": "ai_agent", "label": "Theme Extraction", "ai_model": "claude"}, {"type": "ai_agent", "label": "Priority Ranking", "ai_model": "claude"}, {"type": "output", "label": "Analysis Report"}]},
    {"template_id": "wst_code_review_enhanced", "name": "Code Review Pipeline", "description": "Multi-model security, style, and performance review with merged report", "category": "development", "nodes": [{"type": "input", "label": "Code"}, {"type": "ai_agent", "label": "Security", "ai_model": "claude"}, {"type": "ai_agent", "label": "Style", "ai_model": "chatgpt"}, {"type": "ai_agent", "label": "Performance", "ai_model": "deepseek"}, {"type": "merge", "label": "Merge"}, {"type": "output", "label": "Review Report"}]},
]

# Multilingual
SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native": "English", "rtl": False},
    {"code": "es", "name": "Spanish", "native": "Espanol", "rtl": False},
    {"code": "fr", "name": "French", "native": "Francais", "rtl": False},
    {"code": "de", "name": "German", "native": "Deutsch", "rtl": False},
    {"code": "pt", "name": "Portuguese", "native": "Portugues", "rtl": False},
    {"code": "ja", "name": "Japanese", "native": "Japanese", "rtl": False},
    {"code": "zh", "name": "Chinese", "native": "Chinese", "rtl": False},
    {"code": "ko", "name": "Korean", "native": "Korean", "rtl": False},
    {"code": "ar", "name": "Arabic", "native": "Arabic", "rtl": True},
    {"code": "hi", "name": "Hindi", "native": "Hindi", "rtl": False},
]



class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    avatar_emoji: str = ""
    model: str = "claude"
    system_prompt: str = ""
    tools_enabled: List[str] = []
    knowledge_scope: List[str] = []
    temperature: float = 0.7
    max_tokens: int = 4096
    trigger_keywords: List[str] = []
    auto_respond: bool = False
    can_handoff_to: List[str] = []
    response_style: str = "detailed"  # concise, detailed, structured
    is_public: bool = False


def register_tier23_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Enhanced Agent Builder (#7) ============

    @api_router.post("/agents/custom")
    async def create_custom_agent(data: AgentCreateRequest, request: Request):
        user = await get_current_user(request)
        agent_id = f"ca_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        agent = {
            "agent_id": agent_id, "name": data.name, "avatar_emoji": data.avatar_emoji or "🤖",
            "model": data.model, "system_prompt": data.system_prompt,
            "tools_enabled": data.tools_enabled, "knowledge_scope": data.knowledge_scope,
            "temperature": data.temperature, "max_tokens": data.max_tokens,
            "trigger_keywords": data.trigger_keywords, "auto_respond": data.auto_respond,
            "can_handoff_to": data.can_handoff_to, "response_style": data.response_style,
            "is_public": data.is_public,
            "created_by": user["user_id"], "created_at": now,
        }
        await db.custom_agents.insert_one(agent)
        return {k: v for k, v in agent.items() if k != "_id"}

    @api_router.get("/agents/custom")
    async def list_custom_agents(request: Request, include_public: bool = True):
        user = await get_current_user(request)
        query = {"$or": [{"created_by": user["user_id"]}]}
        if include_public:
            query["$or"].append({"is_public": True})
        agents = await db.custom_agents.find(query, {"_id": 0}).to_list(50)
        return {"agents": agents}

    @api_router.get("/agents/custom/{agent_id}")
    async def get_custom_agent(agent_id: str, request: Request):
        await get_current_user(request)
        agent = await db.custom_agents.find_one({"agent_id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        return agent

    @api_router.put("/agents/custom/{agent_id}")
    async def update_custom_agent(agent_id: str, request: Request):
        user = await get_current_user(request)
        agent = await db.custom_agents.find_one({"agent_id": agent_id})
        if not agent:
            raise HTTPException(404, "Agent not found")
        if agent.get("workspace_id"):
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, agent["workspace_id"])
        elif agent.get("created_by") != user["user_id"]:
            raise HTTPException(403, "Access denied")
        body = await request.json()
        updates = {}
        for key in ["name", "avatar_emoji", "model", "system_prompt", "tools_enabled", "knowledge_scope", "temperature", "max_tokens", "trigger_keywords", "auto_respond", "can_handoff_to", "response_style", "is_public"]:
            if key in body:
                updates[key] = body[key]
        if updates:
            await db.custom_agents.update_one({"agent_id": agent_id}, {"$set": updates})
        return await db.custom_agents.find_one({"agent_id": agent_id}, {"_id": 0})

    @api_router.delete("/agents/custom/{agent_id}")
    async def delete_custom_agent(agent_id: str, request: Request):
        user = await get_current_user(request)
        agent = await db.custom_agents.find_one({"agent_id": agent_id})
        if not agent:
            raise HTTPException(404, "Agent not found")
        if agent.get("workspace_id"):
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, agent["workspace_id"])
        elif agent.get("created_by") != user["user_id"]:
            raise HTTPException(403, "Access denied")
        await db.custom_agents.delete_one({"agent_id": agent_id})
        return {"message": "Deleted"}

    @api_router.post("/agents/custom/{agent_id}/test")
    async def test_custom_agent(agent_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        test_message = body.get("message", "Hello, introduce yourself.")
        agent = await db.custom_agents.find_one({"agent_id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        from ai_providers import call_ai_direct
        from key_resolver import get_integration_key
        from routes_ai_keys import decrypt_key

        KEY_MAP = {
            "chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY",
            "deepseek": "DEEPSEEK_API_KEY", "grok": "XAI_API_KEY", "perplexity": "PERPLEXITY_API_KEY",
            "mistral": "MISTRAL_API_KEY", "cohere": "COHERE_API_KEY", "groq": "GROQ_API_KEY",
        }

        model_key = agent.get("model", "claude")
        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_keys": 1}) or {}
        api_key = None
        encrypted_user_key = (user_doc.get("ai_keys") or {}).get(model_key)
        if encrypted_user_key:
            try:
                api_key = decrypt_key(encrypted_user_key)
            except Exception:
                api_key = None
        if not api_key:
            api_key = await get_integration_key(db, KEY_MAP.get(model_key, "OPENAI_API_KEY"))
        if not api_key:
            logger.info(f"No direct API key configured for {model_key}; attempting live fallback if available")

        system_prompt = f"{agent.get('system_prompt', '').strip()}\n\nResponse style: {agent.get('response_style', 'detailed')}."
        try:
            response = await call_ai_direct(model_key, api_key, system_prompt, test_message, workspace_id=agent.get("workspace_id", ""), db=db)
        except Exception as exc:
            if not api_key:
                raise HTTPException(400, f"No API key configured for {model_key}, and no fallback AI capacity is currently available.")
            raise HTTPException(500, f"Custom agent test failed: {str(exc)[:200]}")

        return {"agent": agent["name"], "model": model_key, "test_input": test_message, "response": response}

    # ============ AI Team Roles (#12) ============

    @api_router.get("/workspaces/{workspace_id}/ai-roles")
    async def list_workspace_roles(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        roles = await db.workspace_ai_roles.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(20)
        return {"roles": roles, "available_roles": AVAILABLE_ROLES}

    @api_router.post("/workspaces/{workspace_id}/ai-roles")
    async def assign_role(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        role_id = f"wr_{uuid.uuid4().hex[:12]}"
        role = {
            "role_id": role_id, "workspace_id": workspace_id,
            "agent_model": body.get("agent_model", "claude"),
            "role_key": body.get("role", ""),
            "custom_prompt_prefix": body.get("custom_prompt", ""),
            "assigned_by": user["user_id"], "created_at": now_iso(),
        }
        await db.workspace_ai_roles.insert_one(role)
        return {k: v for k, v in role.items() if k != "_id"}

    @api_router.delete("/workspaces/{workspace_id}/ai-roles/{role_id}")
    async def remove_role(workspace_id: str, role_id: str, request: Request):
        await _authed_user(request, workspace_id)
        await db.workspace_ai_roles.delete_one({"role_id": role_id, "workspace_id": workspace_id})
        return {"message": "Role removed"}

    # ============ Extended Workflow Templates (#13) ============

    @api_router.get("/workflow-templates/extended")
    async def get_extended_templates(request: Request):
        await get_current_user(request)
        return {"templates": EXTENDED_TEMPLATES}

    # ============ Real-Time Presence (#8) ============

    @api_router.post("/presence/heartbeat")
    async def presence_heartbeat(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        workspace_id = body.get("workspace_id", "")
        await db.user_presence.update_one(
            {"user_id": user["user_id"], "workspace_id": workspace_id},
            {"$set": {"user_id": user["user_id"], "workspace_id": workspace_id, "user_name": user.get("name", ""), "status": "online", "last_seen": now_iso(), "current_tab": body.get("current_tab", "chat")}},
            upsert=True,
        )
        return {"status": "ok"}

    @api_router.get("/workspaces/{workspace_id}/presence")
    async def get_workspace_presence(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        online = await db.user_presence.find({"workspace_id": workspace_id, "last_seen": {"$gte": cutoff}}, {"_id": 0}).to_list(50)
        return {"online_users": online, "count": len(online)}

    @api_router.post("/presence/typing")
    async def typing_indicator(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        # Store typing state (short TTL)
        await db.typing_indicators.update_one(
            {"user_id": user["user_id"], "channel_id": body.get("channel_id", "")},
            {"$set": {"user_id": user["user_id"], "user_name": user.get("name", ""), "channel_id": body.get("channel_id", ""), "is_typing": body.get("is_typing", True), "timestamp": now_iso()}},
            upsert=True,
        )
        return {"status": "ok"}

    @api_router.get("/channels/{channel_id}/typing")
    async def get_typing(channel_id: str, request: Request):
        await get_current_user(request)
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        typing = await db.typing_indicators.find({"channel_id": channel_id, "is_typing": True, "timestamp": {"$gte": cutoff}}, {"_id": 0, "user_name": 1}).to_list(10)
        return {"typing": [t["user_name"] for t in typing]}

    # ============ Export as Deliverables (#9) ============

    @api_router.post("/export/chat-to-document")
    async def export_chat_to_doc(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        channel_id = body.get("channel_id", "")
        msgs = await db.messages.find({"channel_id": channel_id, "sender_type": {"$in": ["human", "ai"]}}, {"_id": 0}).sort("created_at", 1).to_list(200)
        md = "# Chat Export\n\n"
        for m in msgs:
            md += f"**{m.get('sender_name', '')}** ({m.get('created_at', '')[:16]})\n\n{m.get('content', '')}\n\n---\n\n"
        content_id = f"doc_{uuid.uuid4().hex[:12]}"
        await db.generated_content.insert_one({"content_id": content_id, "workspace_id": body.get("workspace_id", ""), "content_type": "document", "title": body.get("title", "Chat Export"), "structure": {"sections": [{"title": "Conversation", "content": md}]}, "version": 1, "created_by": user["user_id"], "created_at": now_iso(), "updated_at": now_iso()})
        return {"content_id": content_id, "format": "document"}

    @api_router.post("/export/chat-to-report")
    async def export_chat_to_report(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        channel_id = body.get("channel_id", "")
        msgs = await db.messages.find({"channel_id": channel_id, "sender_type": {"$in": ["human", "ai"]}}, {"_id": 0}).sort("created_at", 1).to_list(200)
        agents = list({m.get("sender_name") for m in msgs if m.get("sender_type") == "ai"})
        total = len(msgs)
        content_id = f"rpt_{uuid.uuid4().hex[:12]}"
        structure = {
            "sections": [
                {"title": "Summary", "content": f"Conversation with {total} messages across {len(agents)} AI agents: {', '.join(agents)}"},
                {"title": "Key Points", "content": "Key discussion points extracted from the conversation."},
                {"title": "Action Items", "content": "Action items identified during the discussion."},
                {"title": "Full Transcript", "content": "\n".join([f"[{m.get('sender_name','')}]: {m.get('content','')[:200]}" for m in msgs[:50]])},
            ]
        }
        await db.generated_content.insert_one({"content_id": content_id, "workspace_id": body.get("workspace_id", ""), "content_type": "report", "title": body.get("title", "AI Collaboration Report"), "structure": structure, "version": 1, "created_by": user["user_id"], "created_at": now_iso(), "updated_at": now_iso()})
        return {"content_id": content_id, "format": "report"}

    @api_router.post("/export/artifacts-to-document")
    async def combine_artifacts(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        artifact_ids = body.get("artifact_ids") or []
        title = body.get("title", "Combined Document")
        sections = []
        for aid in artifact_ids[:10]:
            art = await db.artifacts.find_one({"artifact_id": aid}, {"_id": 0})
            if art:
                sections.append({"title": art.get("name", "Artifact"), "content": art.get("content", "")})
        content_id = f"doc_{uuid.uuid4().hex[:12]}"
        await db.generated_content.insert_one({"content_id": content_id, "workspace_id": body.get("workspace_id", ""), "content_type": "document", "title": title, "structure": {"sections": sections}, "version": 1, "created_by": user["user_id"], "created_at": now_iso(), "updated_at": now_iso()})
        return {"content_id": content_id, "sections": len(sections)}

    # ============ Multilingual (#11) ============

    @api_router.get("/i18n/languages")
    async def get_supported_languages(request: Request):
        await get_current_user(request)
        return {"languages": SUPPORTED_LANGUAGES}

    # ============ Push Notifications for Mobile (#10) ============

    @api_router.post("/notifications/push-token")
    async def register_push_token(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        await db.push_tokens.update_one(
            {"user_id": user["user_id"], "device_token": body.get("device_token", "")},
            {"$set": {"user_id": user["user_id"], "device_token": body.get("device_token", ""), "device_type": body.get("device_type", "ios"), "registered_at": now_iso()}},
            upsert=True,
        )
        return {"message": "Push token registered"}

    # ============ Voice Notes (#14) ============

    @api_router.post("/voice-notes")
    async def create_voice_note(request: Request):
        user = await get_current_user(request)
        form = await request.form()
        audio = form.get("audio")
        if not audio:
            raise HTTPException(400, "Audio file required")
        import base64
        content = await audio.read()
        note_id = f"vn_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        b64 = base64.b64encode(content).decode("utf-8")
        note = {
            "note_id": note_id, "user_id": user["user_id"],
            "workspace_id": form.get("workspace_id", ""),
            "title": form.get("title", "Voice Note"),
            "mime_type": audio.content_type or "audio/webm",
            "size": len(content),
            "attached_to_type": form.get("attached_to_type"),  # task, artifact
            "attached_to_id": form.get("attached_to_id"),
            "created_at": now,
        }
        await db.voice_notes.insert_one(note)
        await db.voice_note_data.insert_one({"note_id": note_id, "data": b64, "created_at": now})
        return {k: v for k, v in note.items() if k != "_id"}

    @api_router.get("/voice-notes")
    async def list_voice_notes(request: Request, workspace_id: str = ""):
        user = await _authed_user(request, workspace_id)
        query = {"user_id": user["user_id"]}
        if workspace_id:
            query["workspace_id"] = workspace_id
        notes = await db.voice_notes.find(query, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"notes": notes}
