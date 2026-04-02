"""Agent Certification — badge system based on skill proficiency."""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

BADGE_DEFINITIONS = {
    "security-specialist": {"name": "Security Specialist", "description": "Expert in vulnerability detection", "icon": "shield-check", "color": "#EF4444", "requirement": {"skill": "vulnerability_detection", "min_level": "expert"}},
    "code-reviewer-certified": {"name": "Certified Code Reviewer", "description": "Expert-level code review proficiency", "icon": "search-code", "color": "#3B82F6", "requirement": {"skill": "code_review", "min_level": "expert"}},
    "full-stack-master": {"name": "Full-Stack Master", "description": "Expert in code writing, review, and debugging", "icon": "code", "color": "#8B5CF6", "requirement": {"skills": ["code_writing", "code_review", "debugging"], "min_level": "advanced"}},
    "research-guru": {"name": "Research Guru", "description": "Expert researcher and analyst", "icon": "book-open", "color": "#10B981", "requirement": {"skill": "research", "min_level": "expert"}},
    "project-lead": {"name": "Project Lead", "description": "Expert project manager", "icon": "kanban", "color": "#F59E0B", "requirement": {"skill": "project_management", "min_level": "expert"}},
    "fast-responder": {"name": "Fast Responder", "description": "Consistently quick response times", "icon": "zap", "color": "#F97316", "requirement": {"metric": "avg_response_time_ms", "max_value": 2000}},
    "high-confidence": {"name": "High Confidence", "description": "Average confidence above 90%", "icon": "target", "color": "#22C55E", "requirement": {"metric": "avg_confidence", "min_value": 0.9}},
    "streak-master": {"name": "Streak Master", "description": "20+ consecutive successful tasks", "icon": "flame", "color": "#DC2626", "requirement": {"metric": "best_streak", "min_value": 20}},
}

LEVEL_ORDER = {"novice": 0, "intermediate": 1, "advanced": 2, "expert": 3, "master": 4}


async def evaluate_badges(db, agent_id: str, workspace_id: str) -> List[str]:
    """Evaluate which badges an agent qualifies for."""
    agent = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0, "evaluation": 1, "stats": 1})
    if not agent:
        return []
    skills_data = await db.agent_skills.find({"workspace_id": workspace_id, "agent_key": agent_id}, {"_id": 0}).to_list(50)
    skill_levels = {s["skill"]: s.get("level", "novice") for s in skills_data}
    skill_streaks = {s["skill"]: s.get("best_streak", 0) for s in skills_data}
    stats = agent.get("stats") or {}
    earned = []
    for badge_id, badge in BADGE_DEFINITIONS.items():
        req = badge.get("requirement") or {}
        if "skill" in req:
            level = skill_levels.get(req["skill"], "novice")
            if LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER.get(req["min_level"], 3):
                earned.append(badge_id)
        elif "skills" in req:
            all_met = all(LEVEL_ORDER.get(skill_levels.get(s, "novice"), 0) >= LEVEL_ORDER.get(req["min_level"], 2) for s in req["skills"])
            if all_met:
                earned.append(badge_id)
        elif "metric" in req:
            val = stats.get(req["metric"], 0)
            if "min_value" in req and val >= req["min_value"]:
                earned.append(badge_id)
            elif "max_value" in req and 0 < val <= req["max_value"]:
                earned.append(badge_id)
    await db.nexus_agents.update_one({"agent_id": agent_id}, {"$set": {"evaluation.badges": earned}})
    return earned


async def check_and_award_badges(db, workspace_id: str, agent_id: str) -> Dict[str, Any]:
    """Check and award badges to an agent based on skill proficiency (alias for evaluate_badges)."""
    return await evaluate_badges(db, agent_id, workspace_id)
