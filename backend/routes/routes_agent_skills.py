"""Agent Skills Matrix routes — CRUD, proficiency tracking, assessments, leaderboard."""
import uuid
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List
from agent_skill_definitions import BUILTIN_SKILLS, SKILL_CATEGORIES, get_all_skill_ids

logger = logging.getLogger(__name__)


class CreateSkill(BaseModel):
    skill_id: str = Field(..., min_length=2, max_length=50)
    category: str = "engineering"
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    icon: str = "star"
    color: str = "#6366f1"


class RunAssessment(BaseModel):
    skill_ids: List[str] = Field(default_factory=list)


def register_agent_skills_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.get("/skills")
    async def list_skills(category: Optional[str] = None):
        """List all skill definitions (builtin + custom)."""
        skills = list(BUILTIN_SKILLS.values())
        custom = await db.skill_definitions.find({"is_builtin": False}, {"_id": 0}).to_list(100)
        skills.extend(custom)
        if category:
            skills = [s for s in skills if s.get("category") == category]
        return {"skills": skills, "categories": SKILL_CATEGORIES}

    @api_router.get("/skills/{skill_id}")
    async def get_skill_detail(skill_id: str):
        """Get a specific skill definition with assessment info."""
        skill = BUILTIN_SKILLS.get(skill_id)
        if not skill:
            skill = await db.skill_definitions.find_one({"skill_id": skill_id}, {"_id": 0})
        if not skill:
            raise HTTPException(404, "Skill not found")
        return skill

    @api_router.post("/skills")
    async def create_custom_skill(data: CreateSkill, request: Request):
        """Create a custom skill definition (admin)."""
        user = await get_current_user(request)
        if data.skill_id in BUILTIN_SKILLS:
            raise HTTPException(400, "Skill ID conflicts with builtin skill")
        existing = await db.skill_definitions.find_one({"skill_id": data.skill_id})
        if existing:
            raise HTTPException(400, "Skill ID already exists")
        skill = {
            "skill_id": data.skill_id, "category": data.category, "name": data.name,
            "description": data.description, "icon": data.icon, "color": data.color,
            "recommended_tools": [], "prompt_injection": {}, "assessment_prompts": [],
            "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
            "is_builtin": False, "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.skill_definitions.insert_one(skill)
        skill.pop("_id", None)
        return skill

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/skills")
    async def get_agent_skills(ws_id: str, agent_id: str, request: Request):
        """Get agent's skill proficiency matrix."""
        user = await _authed_user(request, ws_id)
        records = await db.agent_skills.find(
            {"workspace_id": ws_id, "agent_key": agent_id}, {"_id": 0}
        ).to_list(100)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "skills": 1, "evaluation": 1})
        configured_skills = agent.get("skills") or [] if agent else []
        return {"proficiency": records, "configured_skills": configured_skills, "evaluation": agent.get("evaluation") or {}}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/skills/assess")
    async def run_skill_assessment(ws_id: str, agent_id: str, data: RunAssessment, request: Request):
        """Run automated skill assessment for an agent."""
        user = await _authed_user(request, ws_id)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        skill_ids = data.skill_ids or [s["skill_id"] for s in agent.get("skills") or []]
        if not skill_ids:
            raise HTTPException(400, "No skills to assess")

        # Use real AI-powered assessment
        from agent_evaluator import run_real_assessment
        result = await run_real_assessment(db, ws_id, agent_id, skill_ids=skill_ids)
        return result

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/skills/history")
    async def get_skill_history(ws_id: str, agent_id: str, request: Request, skill: Optional[str] = None):
        """Get proficiency history over time."""
        user = await _authed_user(request, ws_id)
        query = {"workspace_id": ws_id, "agent_key": agent_id}
        if skill:
            query["skill"] = skill
        records = await db.agent_skills.find(query, {"_id": 0}).to_list(100)
        return {"history": records}

    @api_router.get("/workspaces/{ws_id}/skills/leaderboard")
    async def workspace_skill_leaderboard(ws_id: str, request: Request, skill: Optional[str] = None):
        """Workspace skill leaderboard across all agents."""
        user = await _authed_user(request, ws_id)
        query = {"workspace_id": ws_id}
        if skill:
            query["skill"] = skill
        records = await db.agent_skills.find(query, {"_id": 0}).sort("proficiency", -1).limit(50).to_list(50)
        return {"leaderboard": records}
