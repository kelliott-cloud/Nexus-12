"""Agent Creator Studio routes — wizard, versioning, clone, publish, preview."""
import uuid
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List
from agent_skill_definitions import BUILTIN_SKILLS, get_all_skill_ids

logger = logging.getLogger(__name__)

AGENT_CATEGORIES = ["engineering", "product", "design", "qa", "ops", "research", "support", "custom"]
TONES = ["precise", "friendly", "formal", "creative", "terse"]
VERBOSITY = ["brief", "balanced", "detailed"]
RISK_TOLERANCE = ["conservative", "moderate", "aggressive"]
COLLAB_STYLES = ["leader", "contributor", "reviewer", "specialist"]


class SkillConfig(BaseModel):
    skill_id: str
    level: str = "intermediate"
    priority: int = 2
    custom_instructions: str = ""


class PersonalityConfig(BaseModel):
    tone: str = "balanced"
    verbosity: str = "balanced"
    risk_tolerance: str = "moderate"
    collaboration_style: str = "contributor"


class GuardrailsConfig(BaseModel):
    max_response_length: int = 4000
    require_citations: bool = False
    require_confidence: bool = True
    forbidden_topics: List[str] = []
    escalation_threshold: float = 0.4
    auto_handoff_agents: List[str] = []


class StudioCreateAgent(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field("", max_length=500)
    base_model: str
    system_prompt: str = Field("", max_length=10000)
    color: str = "#6366F1"
    category: str = "custom"
    tags: List[str] = []
    skills: List[SkillConfig] = []
    allowed_tools: List[str] = []
    denied_tools: List[str] = []
    personality: Optional[PersonalityConfig] = None
    guardrails: Optional[GuardrailsConfig] = None
    preferred_role: str = "contributor"


class StudioUpdateAgent(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_model: Optional[str] = None
    system_prompt: Optional[str] = None
    color: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    skills: Optional[List[SkillConfig]] = None
    allowed_tools: Optional[List[str]] = None
    denied_tools: Optional[List[str]] = None
    personality: Optional[PersonalityConfig] = None
    guardrails: Optional[GuardrailsConfig] = None
    preferred_role: Optional[str] = None


def register_agent_studio_routes(api_router, db, get_current_user, AI_MODELS):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/agents/studio")
    async def create_studio_agent(ws_id: str, data: StudioCreateAgent, request: Request):
        """Create agent via studio wizard with full config."""
        user = await _authed_user(request, ws_id)
        workspace = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        if data.base_model not in AI_MODELS:
            raise HTTPException(400, f"Invalid base model: {data.base_model}")

        agent_id = f"nxa_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        agent = {
            "agent_id": agent_id, "workspace_id": ws_id, "created_by": user["user_id"],
            "name": data.name, "description": data.description,
            "base_model": data.base_model, "system_prompt": data.system_prompt,
            "color": data.color, "avatar": data.name[:2].upper(),
            "version": 1, "version_history": [],
            "status": "active", "visibility": "workspace",
            "category": data.category, "tags": data.tags[:10],
            "personality": data.personality.dict() if data.personality else {},
            "skills": [s.dict() for s in data.skills],
            "allowed_tools": data.allowed_tools, "denied_tools": data.denied_tools,
            "guardrails": data.guardrails.dict() if data.guardrails else {},
            "preferred_role": data.preferred_role,
            "evaluation": {"last_assessed": None, "overall_score": 0, "skill_scores": {}, "badges": [], "arena_elo": 1200, "arena_matches": 0},
            "stats": {"total_messages": 0, "total_tool_calls": 0, "avg_confidence": 0, "avg_response_time_ms": 0, "total_cost_usd": 0, "channels_active_in": 0, "last_active": None},
            "training": {"enabled": False, "total_chunks": 0, "total_sources": 0, "total_sessions": 0, "knowledge_token_budget": 3000, "retrieval_strategy": "semantic", "min_relevance_score": 0.3},
            "forked_from": None, "fork_count": 0,
            "created_at": now, "updated_at": now,
        }
        await db.nexus_agents.insert_one(agent)
        agent.pop("_id", None)
        return agent

    @api_router.put("/workspaces/{ws_id}/agents/{agent_id}/studio")
    async def update_studio_agent(ws_id: str, agent_id: str, data: StudioUpdateAgent, request: Request):
        """Update agent via studio — auto-increments version."""
        user = await _authed_user(request, ws_id)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        now = datetime.now(timezone.utc).isoformat()
        old_version = {"version": agent.get("version", 1), "system_prompt": agent.get("system_prompt", ""), "skills": agent.get("skills") or [], "updated_at": agent.get("updated_at", now), "updated_by": user["user_id"]}
        history = agent.get("version_history") or [][-9:]
        history.append(old_version)

        updates = {"updated_at": now, "version": agent.get("version", 1) + 1, "version_history": history}
        for field in ["name", "description", "base_model", "system_prompt", "color", "category", "tags", "allowed_tools", "denied_tools", "preferred_role"]:
            val = getattr(data, field, None)
            if val is not None:
                updates[field] = val
        if data.name:
            updates["avatar"] = data.name[:2].upper()
        if data.skills is not None:
            updates["skills"] = [s.dict() for s in data.skills]
        if data.personality is not None:
            updates["personality"] = data.personality.dict()
        if data.guardrails is not None:
            updates["guardrails"] = data.guardrails.dict()

        await db.nexus_agents.update_one({"agent_id": agent_id}, {"$set": updates})
        updated = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0})
        return updated

    # Agent versions handled by routes_agent_versioning.py

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/rollback/{version}")
    async def rollback_agent(ws_id: str, agent_id: str, version: int, request: Request):
        """Rollback to a previous version."""
        user = await _authed_user(request, ws_id)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        target = next((v for v in agent.get("version_history") or [] if v.get("version") == version), None)
        if not target:
            raise HTTPException(404, f"Version {version} not found")
        updates = {"system_prompt": target["system_prompt"], "skills": target.get("skills") or [], "updated_at": datetime.now(timezone.utc).isoformat(), "version": agent.get("version", 1) + 1}
        await db.nexus_agents.update_one({"agent_id": agent_id}, {"$set": updates})
        return {"status": "rolled_back", "to_version": version, "new_version": updates["version"]}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/clone")
    async def clone_agent(ws_id: str, agent_id: str, request: Request):
        """Clone an agent into the same workspace."""
        user = await _authed_user(request, ws_id)
        source = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0})
        if not source:
            raise HTTPException(404, "Agent not found")
        new_id = f"nxa_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        clone = {**source, "agent_id": new_id, "name": f"{source['name']} (Clone)", "created_by": user["user_id"], "version": 1, "version_history": [], "forked_from": agent_id, "fork_count": 0, "stats": {"total_messages": 0, "total_tool_calls": 0, "avg_confidence": 0, "avg_response_time_ms": 0, "total_cost_usd": 0, "channels_active_in": 0, "last_active": None}, "created_at": now, "updated_at": now}
        await db.nexus_agents.insert_one(clone)
        await db.nexus_agents.update_one({"agent_id": agent_id}, {"$inc": {"fork_count": 1}})
        clone.pop("_id", None)
        return clone

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/publish")
    async def publish_agent(ws_id: str, agent_id: str, request: Request):
        """Publish agent to marketplace catalog."""
        user = await _authed_user(request, ws_id)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        from routes_agent_marketplace import AgentPublish
        pub = AgentPublish(name=agent["name"], description=agent.get("description", ""), category=agent.get("category", "custom"), base_model=agent["base_model"], system_prompt=agent.get("system_prompt", ""), tags=agent.get("tags") or [], color=agent.get("color", "#6366f1"))
        # Reuse marketplace publish logic
        mkt_id = f"mkt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        entry = {"agent_id": mkt_id, "name": pub.name, "description": pub.description, "category": pub.category, "base_model": pub.base_model, "system_prompt": pub.system_prompt, "tags": pub.tags, "icon": agent.get("avatar", pub.name[0]), "color": pub.color, "creator_id": user["user_id"], "creator_name": user.get("name", "Anonymous"), "status": "published", "installs": 0, "avg_rating": 0, "rating_count": 0, "ratings": [], "skills": agent.get("skills") or [], "personality": agent.get("personality") or {}, "guardrails": agent.get("guardrails") or {}, "source_agent_id": agent_id, "created_at": now, "updated_at": now}
        await db.agent_marketplace.insert_one(entry)
        entry.pop("_id", None)
        await db.nexus_agents.update_one({"agent_id": agent_id}, {"$set": {"visibility": "marketplace"}})
        return {"status": "published", "marketplace_id": mkt_id}

    @api_router.patch("/workspaces/{ws_id}/agents/{agent_id}/status")
    async def update_agent_status(ws_id: str, agent_id: str, request: Request):
        """Update agent status (active/paused/archived)."""
        user = await _authed_user(request, ws_id)
        body = await request.json()
        new_status = body.get("status", "active")
        if new_status not in ("active", "paused", "draft", "archived"):
            raise HTTPException(400, "Invalid status")
        await db.nexus_agents.update_one({"agent_id": agent_id, "workspace_id": ws_id}, {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"status": new_status}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/preview")
    async def preview_agent(ws_id: str, agent_id: str, request: Request):
        """Preview agent behavior with a test prompt."""
        user = await _authed_user(request, ws_id)
        body = await request.json()
        test_prompt = body.get("prompt", "Hello, introduce yourself and describe your capabilities.")
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        from agent_prompt_builder import build_agent_prompt
        assembled = await build_agent_prompt(db, agent, ws_id, "")
        return {"agent_id": agent_id, "assembled_prompt_preview": assembled[:2000], "prompt_length": len(assembled), "test_prompt": test_prompt, "note": "Full AI response requires API key. This shows the assembled system prompt."}
