"""Context Ledger — Tracks agent context switches for seamless work resumption.

When agents are interrupted (by humans or other agents), the ledger records:
- What the agent was working on (prior context)
- What triggered the switch (human question, agent disagreement, etc.)
- The agent's response to the trigger
- A resume point so the agent can pick back up without repeating itself

This prevents redundant responses and enables agents to maintain continuity
across interruptions and disagreements.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def register_context_ledger_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.get("/channels/{channel_id}/context-ledger")
    async def get_channel_context_ledger(channel_id: str, request: Request, limit: int = 30):
        """Get context ledger entries for a channel"""
        await get_current_user(request)
        entries = await db.context_ledger.find(
            {"channel_id": channel_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"entries": entries}

    @api_router.get("/admin/context-ledger")
    async def get_org_context_ledger(request: Request, workspace_id: str = None, channel_id: str = None,
                                      agent: str = None, event_type: str = None, limit: int = 50):
        """Org admin view of context ledger across all channels/projects"""
        user = await _authed_user(request, workspace_id)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            # Check if user is org admin
            org_admin = await db.org_memberships.find_one(
                {"user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
            )
            if not org_admin:
                raise HTTPException(403, "Admin access required")

        query = {}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if channel_id:
            query["channel_id"] = channel_id
        if agent:
            query["agent_key"] = agent
        if event_type:
            query["event_type"] = event_type

        entries = await db.context_ledger.find(
            query, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)

        # Enrich with channel/project names
        for entry in entries:
            ch = await db.channels.find_one({"channel_id": entry.get("channel_id", "")}, {"_id": 0, "name": 1})
            entry["channel_name"] = ch.get("name", "") if ch else ""
            if entry.get("project_id"):
                proj = await db.projects.find_one({"project_id": entry["project_id"]}, {"_id": 0, "name": 1})
                entry["project_name"] = proj.get("name", "") if proj else ""

        return {"entries": entries, "total": len(entries)}

    @api_router.get("/admin/context-ledger/stats")
    async def get_context_ledger_stats(request: Request):
        """Get aggregate stats for context switching activity"""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            org_admin = await db.org_memberships.find_one(
                {"user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
            )
            if not org_admin:
                raise HTTPException(403, "Admin access required")

        total = await db.context_ledger.count_documents({})
        by_type = {}
        for etype in ["context_save", "context_switch", "context_resume", "disagreement", "human_interrupt"]:
            by_type[etype] = await db.context_ledger.count_documents({"event_type": etype})

        # Most active agents in context switching
        pipeline = [
            {"$group": {"_id": "$agent_key", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        agent_counts = await db.context_ledger.aggregate(pipeline).to_list(10)

        return {
            "total_entries": total,
            "by_type": by_type,
            "top_agents": [{"agent": a["_id"], "count": a["count"]} for a in agent_counts],
        }


async def save_context_entry(db, channel_id, workspace_id, agent_key, agent_name,
                              event_type, prior_work, trigger, trigger_source,
                              response_summary="", project_id=None):
    """Save a context ledger entry. Called by the collaboration engine."""
    entry = {
        "ledger_id": f"ctx_{uuid.uuid4().hex[:12]}",
        "channel_id": channel_id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "agent_key": agent_key,
        "agent_name": agent_name,
        "event_type": event_type,
        "prior_work": prior_work[:500] if prior_work else "",
        "trigger": trigger[:500] if trigger else "",
        "trigger_source": trigger_source,
        "response_summary": response_summary[:500] if response_summary else "",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.context_ledger.insert_one(entry)
    return entry["ledger_id"]


async def get_agent_prior_context(db, channel_id, agent_key, limit=3):
    """Get the most recent context entries for an agent in a channel.
    Used to build the context awareness prompt."""
    entries = await db.context_ledger.find(
        {"channel_id": channel_id, "agent_key": agent_key},
        {"_id": 0, "event_type": 1, "prior_work": 1, "trigger": 1,
         "trigger_source": 1, "response_summary": 1, "created_at": 1}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return entries


def build_context_awareness_prompt(prior_entries, agent_name):
    """Build a prompt section that makes agents aware of their context history."""
    if not prior_entries:
        return ""

    prompt = f"\n\n=== CONTEXT CONTINUITY LOG ({agent_name}) ===\n"
    prompt += "Review your recent context switches below. DO NOT repeat work you've already done.\n"
    prompt += "If resuming after an interruption, briefly acknowledge and continue from where you left off.\n\n"

    for entry in reversed(prior_entries):
        etype = entry.get("event_type", "")
        if etype == "human_interrupt":
            prompt += f"- [Human interruption] Trigger: \"{entry.get('trigger', '')[:150]}\"\n"
            if entry.get("prior_work"):
                prompt += f"  You were working on: {entry['prior_work'][:150]}\n"
        elif etype == "disagreement":
            prompt += f"- [Disagreement with {entry.get('trigger_source', 'another agent')}] About: \"{entry.get('trigger', '')[:150]}\"\n"
        elif etype == "context_switch":
            prompt += f"- [Context switch from {entry.get('trigger_source', '?')}] Topic: \"{entry.get('trigger', '')[:150]}\"\n"
            if entry.get("prior_work"):
                prompt += f"  Prior work: {entry['prior_work'][:150]}\n"

    prompt += "\nIMPORTANT: Do NOT re-explain or repeat responses you've already given. "
    prompt += "Reference prior work and build on it. If asked the same thing again, say you've already addressed it and summarize briefly.\n"
    prompt += "=== END CONTEXT LOG ===\n"
    return prompt
