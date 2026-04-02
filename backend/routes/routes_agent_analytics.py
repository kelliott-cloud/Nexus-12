"""Agent Analytics routes — performance dashboards, comparison, cost breakdown."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from typing import Optional

logger = logging.getLogger(__name__)


def register_agent_analytics_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/analytics")
    async def get_agent_analytics(ws_id: str, agent_id: str, request: Request, days: int = 30):
        """Full agent performance dashboard."""
        await get_current_user(request)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "stats": 1, "evaluation": 1, "skills": 1, "name": 1, "base_model": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")
        skills = await db.agent_skills.find({"workspace_id": ws_id, "agent_key": agent_id}, {"_id": 0}).to_list(50)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent_messages = await db.messages.count_documents({"sender_id": agent_id, "created_at": {"$gte": cutoff}})
        training = await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": {"$ne": True}})
        return {
            "agent": {"agent_id": agent_id, "name": agent.get("name"), "base_model": agent.get("base_model")},
            "stats": agent.get("stats") or {},
            "evaluation": agent.get("evaluation") or {},
            "skills": skills,
            "configured_skills": agent.get("skills") or [],
            "recent_messages": recent_messages,
            "training_chunks": training,
            "period_days": days,
        }

    @api_router.get("/workspaces/{ws_id}/agents/compare")
    async def compare_agents(ws_id: str, request: Request, agents: str = ""):
        """Compare 2-4 agents side-by-side."""
        await get_current_user(request)
        agent_ids = [a.strip() for a in agents.split(",") if a.strip()][:4]
        if len(agent_ids) < 2:
            raise HTTPException(400, "Provide at least 2 agent IDs (comma-separated)")
        results = []
        for aid in agent_ids:
            agent = await db.nexus_agents.find_one({"agent_id": aid, "workspace_id": ws_id}, {"_id": 0, "name": 1, "base_model": 1, "stats": 1, "evaluation": 1, "skills": 1, "color": 1})
            if agent:
                skill_records = await db.agent_skills.find({"workspace_id": ws_id, "agent_key": aid}, {"_id": 0}).to_list(50)
                results.append({**agent, "agent_id": aid, "skill_proficiency": skill_records})
        return {"agents": results}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/cost-breakdown")
    async def agent_cost_breakdown(ws_id: str, agent_id: str, request: Request, days: int = 30):
        """Per-skill cost breakdown from AI call instrumentation."""
        await get_current_user(request)
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "stats": 1, "name": 1, "skills": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        skills = [s.get("skill_id") for s in agent.get("skills") or []]

        # Get cost events from reporting
        cost_pipeline = [
            {"$match": {"workspace_id": ws_id, "agent_key": agent_id, "timestamp": {"$gte": since}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$dateFromString": {"dateString": "$timestamp"}}}},
                "calls": {"$sum": 1},
                "estimated_cost": {"$sum": "$estimated_cost_usd"},
                "tokens_in": {"$sum": "$tokens_in"},
                "tokens_out": {"$sum": "$tokens_out"},
            }},
            {"$sort": {"_id": 1}},
        ]
        daily_costs = await db.ai_events.aggregate(cost_pipeline).to_list(60)
        total_cost = sum(d.get("estimated_cost") or 0 for d in daily_costs)
        total_calls = sum(d.get("calls") or 0 for d in daily_costs)

        # Distribute cost proportionally across configured skills
        skill_costs = {}
        if skills and total_calls > 0:
            per_skill_cost = total_cost / len(skills)
            for sid in skills:
                skill_costs[sid] = round(per_skill_cost, 4)

        return {
            "agent_id": agent_id,
            "name": agent.get("name"),
            "total_cost_usd": round(total_cost, 4),
            "total_calls": total_calls,
            "period_days": days,
            "daily_costs": [{"date": d["_id"], "calls": d["calls"], "cost": round(d.get("estimated_cost") or 0, 4)} for d in daily_costs],
            "skill_costs": skill_costs,
        }
