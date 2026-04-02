"""Agent Context Builder — Assembles rich situational awareness block for every agent turn.

Injects: agent status, workspace info, project deadlines, cost tracking, assignments,
time context, alerts, and human profile. ~200 tokens, massive improvement in coherence.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


async def _build_workspace_context(db, workspace_id: str) -> Optional[str]:
    """Fetch workspace name and member count."""
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "name": 1})
    if not ws:
        return None
    members = await db.workspace_members.count_documents({"workspace_id": workspace_id})
    return f"[WORKSPACE] {ws.get('name', '?')} | Members: {members}"


async def _build_project_context(db, workspace_id: str, now: datetime) -> Optional[str]:
    """Fetch active projects with deadline info."""
    projects = await db.projects.find(
        {"workspace_id": workspace_id, "status": {"$in": ["active", "in_progress"]}},
        {"_id": 0, "name": 1, "project_id": 1, "deadline": 1, "status": 1}
    ).limit(3).to_list(3)
    if not projects:
        return None
    proj_strs = []
    for p in projects:
        s = f"{p['name']} ({p['status']})"
        if p.get("deadline"):
            try:
                dl = datetime.fromisoformat(p["deadline"].replace("Z", "+00:00"))
                days_left = (dl - now).days
                s += f" — {days_left}d left"
            except Exception:
                pass
        proj_strs.append(s)
    return f"[PROJECTS] {' | '.join(proj_strs)}"


async def _build_assignment_context(db, workspace_id: str, agent_key: str) -> Optional[str]:
    """Fetch pending assignments for this agent."""
    assignments = await db.work_queue.find(
        {"workspace_id": workspace_id, "assigned_to": agent_key, "status": {"$in": ["pending", "in_progress"]}},
        {"_id": 0, "title": 1, "status": 1, "priority": 1}
    ).limit(5).to_list(5)
    if not assignments:
        return None
    blocking = [a for a in assignments if a.get("priority", 5) <= 2]
    return f"[ASSIGNMENTS] {len(assignments)} tasks | {len(blocking)} blocking"


async def _build_cost_context(db, workspace_id: str, now: datetime) -> str:
    """Calculate daily cost and budget info."""
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    daily_events = await db.reporting_events.find(
        {"workspace_id": workspace_id,
         "created_at": {"$gte": today_start.isoformat(), "$lt": tomorrow_start.isoformat()},
         "event_type": "ai_call"},
        {"_id": 0, "estimated_cost_usd": 1}
    ).limit(200).to_list(200)
    daily_cost = sum(e.get("estimated_cost_usd", 0) for e in daily_events)
    budget = await db.workspace_budgets.find_one({"workspace_id": workspace_id}, {"_id": 0, "monthly_cap_usd": 1})
    budget_str = f"Budget: ${budget['monthly_cap_usd']}" if budget and budget.get("monthly_cap_usd") else "No cap"
    return f"[COST] Today: ${daily_cost:.2f} | {budget_str}"


async def _build_user_context(db, owner_id: str) -> Optional[str]:
    """Fetch human user profile."""
    user = await db.users.find_one({"user_id": owner_id}, {"_id": 0, "name": 1, "platform_role": 1, "plan": 1})
    if not user:
        return None
    return f"[USER] {user.get('name', '?')} | {user.get('platform_role', 'member')} | {user.get('plan', 'free')} plan"


async def _build_feedback_context(db, channel_id: str, agent_key: str) -> Optional[str]:
    """Check recent reactions on this agent's messages."""
    recent_reactions = await db.messages.find(
        {"channel_id": channel_id, "sender_id": agent_key, "reactions": {"$exists": True, "$ne": {}}},
        {"_id": 0, "reactions": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    thumbs_up = sum(1 for m in recent_reactions if (m.get("reactions") or {}).get("thumbs_up"))
    thumbs_down = sum(1 for m in recent_reactions if (m.get("reactions") or {}).get("thumbs_down"))
    if not thumbs_up and not thumbs_down:
        return None
    return f"[FEEDBACK] Recent: {thumbs_up} positive, {thumbs_down} negative"


async def _build_skills_context(db, workspace_id: str, agent_key: str) -> Optional[str]:
    """Fetch agent skill profile."""
    skills_data = await db.agent_skills.find(
        {"workspace_id": workspace_id, "agent_key": agent_key},
        {"_id": 0, "skill": 1, "level": 1, "proficiency": 1}
    ).sort("proficiency", -1).limit(5).to_list(5)
    if not skills_data:
        return None
    skill_strs = [f"{s['skill']}({s.get('level', '?')})" for s in skills_data]
    return f"[SKILLS] {' | '.join(skill_strs)}"


async def _build_badges_context(db, agent_key: str) -> Optional[str]:
    """Fetch agent evaluation badges."""
    agent_doc = await db.nexus_agents.find_one(
        {"agent_id": agent_key}, {"_id": 0, "evaluation.badges": 1}
    )
    badges = (agent_doc.get("evaluation") or {}).get("badges") or [] if agent_doc else []
    if not badges:
        return None
    return f"[BADGES] {', '.join(badges[:5])}"


async def build_agent_context_block(
    db, agent_key: str, model_name: str, workspace_id: str,
    channel_id: str, owner_id: str, turn_number: int = 0
) -> str:
    """Build structured context block injected at top of every agent prompt."""
    now = datetime.now(timezone.utc)
    parts: List[str] = []

    try:
        parts.append(f"[AGENT] {model_name} | Role: {agent_key} | Turn: {turn_number}")

        builders = [
            _build_workspace_context(db, workspace_id),
            _build_project_context(db, workspace_id, now),
            _build_assignment_context(db, workspace_id, agent_key),
            _build_cost_context(db, workspace_id, now),
        ]
        # Gather workspace, project, assignment, cost in parallel
        import asyncio
        results = await asyncio.gather(*builders, return_exceptions=True)
        for r in results:
            if isinstance(r, str):
                parts.append(r)

        parts.append(f"[TIME] UTC: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")

        # User, feedback, skills, badges
        user_ctx = await _build_user_context(db, owner_id)
        if user_ctx:
            parts.append(user_ctx)

        feedback_ctx = await _build_feedback_context(db, channel_id, agent_key)
        if feedback_ctx:
            parts.append(feedback_ctx)

        try:
            skills_ctx = await _build_skills_context(db, workspace_id, agent_key)
            if skills_ctx:
                parts.append(skills_ctx)
        except Exception:
            pass

        try:
            badges_ctx = await _build_badges_context(db, agent_key)
            if badges_ctx:
                parts.append(badges_ctx)
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"Context block build error: {e}")

    if not parts:
        return ""

    return "\n=== AGENT STATUS ===\n" + "\n".join(parts) + "\n=== END STATUS ===\n"
