"""Training Analytics — Knowledge effectiveness, gap detection, time-series metrics.

Tracks which chunks lead to good responses, identifies knowledge gaps,
and provides time-series data for training activity visualization.
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Request

logger = logging.getLogger(__name__)


def register_training_analytics_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/analytics/effectiveness")
    async def knowledge_effectiveness(ws_id: str, agent_id: str, request: Request):
        """Rank knowledge chunks by effectiveness (retrievals × helpfulness ratio)."""
        await get_current_user(request)
        pipeline = [
            {"$match": {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}}},
            {"$project": {
                "_id": 0, "chunk_id": 1, "topic": 1, "category": 1,
                "content": {"$substr": ["$content", 0, 150]},
                "quality_score": 1, "times_retrieved": {"$ifNull": ["$times_retrieved", 0]},
                "times_helpful": {"$ifNull": ["$times_helpful", 0]},
                "source.domain": 1,
            }},
            {"$addFields": {
                "helpfulness_ratio": {
                    "$cond": [
                        {"$gt": ["$times_retrieved", 0]},
                        {"$divide": ["$times_helpful", "$times_retrieved"]},
                        0
                    ]
                },
                "effectiveness_score": {
                    "$multiply": [
                        {"$ifNull": ["$quality_score", 0.5]},
                        {"$add": [{"$ifNull": ["$times_retrieved", 0]}, 1]},
                        {"$add": [
                            {"$cond": [
                                {"$gt": ["$times_retrieved", 0]},
                                {"$divide": ["$times_helpful", "$times_retrieved"]},
                                0.5
                            ]},
                            0.1
                        ]}
                    ]
                }
            }},
            {"$sort": {"effectiveness_score": -1}},
            {"$limit": 30},
        ]
        top = await db.agent_knowledge.aggregate(pipeline).to_list(30)

        # Bottom performers
        bottom_pipeline = [
            {"$match": {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}, "times_retrieved": {"$gt": 2}}},
            {"$project": {
                "_id": 0, "chunk_id": 1, "topic": 1, "category": 1,
                "content": {"$substr": ["$content", 0, 150]},
                "quality_score": 1, "times_retrieved": 1, "times_helpful": 1,
            }},
            {"$addFields": {
                "helpfulness_ratio": {"$divide": [{"$ifNull": ["$times_helpful", 0]}, {"$max": ["$times_retrieved", 1]}]},
            }},
            {"$match": {"helpfulness_ratio": {"$lt": 0.3}}},
            {"$sort": {"helpfulness_ratio": 1}},
            {"$limit": 10},
        ]
        bottom = await db.agent_knowledge.aggregate(bottom_pipeline).to_list(10)

        return {
            "top_performers": top,
            "low_performers": bottom,
            "total_chunks": await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": {"$ne": True}}),
            "chunks_used": await db.agent_knowledge.count_documents({"agent_id": agent_id, "times_retrieved": {"$gt": 0}}),
        }

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/analytics/gaps")
    async def knowledge_gaps(ws_id: str, agent_id: str, request: Request):
        """Identify knowledge gaps — topics with low coverage or no chunks."""
        await get_current_user(request)

        # Get agent skills
        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id}, {"_id": 0, "skills": 1}
        )
        skills = agent.get("skills") or [] if agent else []
        skill_names = [s.get("skill_id", "").replace("_", " ") for s in skills if s.get("priority", 99) <= 3]

        # Coverage per topic
        topic_pipeline = [
            {"$match": {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}}},
            {"$group": {
                "_id": "$topic",
                "chunk_count": {"$sum": 1},
                "avg_quality": {"$avg": "$quality_score"},
                "total_retrievals": {"$sum": {"$ifNull": ["$times_retrieved", 0]}},
                "total_helpful": {"$sum": {"$ifNull": ["$times_helpful", 0]}},
            }},
            {"$sort": {"chunk_count": -1}},
        ]
        topics = await db.agent_knowledge.aggregate(topic_pipeline).to_list(50)

        # Category coverage
        cat_pipeline = [
            {"$match": {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "avg_quality": {"$avg": "$quality_score"},
            }},
        ]
        categories = {c["_id"]: c for c in await db.agent_knowledge.aggregate(cat_pipeline).to_list(20)}

        # Identify gaps: skills without matching knowledge
        gaps = []
        for skill_name in skill_names:
            matching_topics = [t for t in topics if skill_name.lower() in (t["_id"] or "").lower()]
            if not matching_topics:
                gaps.append({"skill": skill_name, "type": "no_training", "severity": "high", "suggestion": f"Add training on: {skill_name}"})
            elif all(t["chunk_count"] < 3 for t in matching_topics):
                gaps.append({"skill": skill_name, "type": "low_coverage", "severity": "medium", "suggestion": f"Only {sum(t['chunk_count'] for t in matching_topics)} chunks for {skill_name}. Consider deeper training."})

        # Check for category imbalances
        ideal_cats = {"concept", "procedure", "example", "warning", "reference"}
        existing_cats = set(categories.keys())
        missing_cats = ideal_cats - existing_cats
        for cat in missing_cats:
            gaps.append({"skill": cat, "type": "missing_category", "severity": "low", "suggestion": f"No '{cat}' knowledge chunks. Consider adding {cat}-type content."})

        return {
            "gaps": gaps,
            "topic_coverage": [{
                "topic": t["_id"],
                "chunk_count": t["chunk_count"],
                "avg_quality": round(t["avg_quality"], 2) if t["avg_quality"] else 0,
                "total_retrievals": t["total_retrievals"],
            } for t in topics],
            "category_distribution": {k: {"count": v["count"], "avg_quality": round(v["avg_quality"], 2) if v["avg_quality"] else 0} for k, v in categories.items()},
            "agent_skills": skill_names,
        }

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/analytics/timeseries")
    async def training_timeseries(ws_id: str, agent_id: str, request: Request, days: int = 30):
        """Time-series data: training activity, knowledge growth, usage over time."""
        await get_current_user(request)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Knowledge growth over time (chunks created per day)
        growth_pipeline = [
            {"$match": {"agent_id": agent_id, "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "new_chunks": {"$sum": 1},
                "avg_quality": {"$avg": "$quality_score"},
            }},
            {"$sort": {"_id": 1}},
        ]
        growth = await db.agent_knowledge.aggregate(growth_pipeline).to_list(days)

        # Session activity over time
        session_pipeline = [
            {"$match": {"agent_id": agent_id, "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "sessions": {"$sum": 1},
                "total_chunks": {"$sum": "$total_chunks"},
            }},
            {"$sort": {"_id": 1}},
        ]
        session_activity = await db.agent_training_sessions.aggregate(session_pipeline).to_list(days)

        # Retrieval activity (from agent knowledge updates)
        retrieval_pipeline = [
            {"$match": {"agent_id": agent_id, "last_retrieved": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$substr": ["$last_retrieved", 0, 10]},
                "retrievals": {"$sum": "$times_retrieved"},
                "helpful": {"$sum": "$times_helpful"},
            }},
            {"$sort": {"_id": 1}},
        ]
        retrievals = await db.agent_knowledge.aggregate(retrieval_pipeline).to_list(days)

        # Build unified timeline
        all_dates = set()
        for g in growth:
            all_dates.add(g["_id"])
        for s in session_activity:
            all_dates.add(s["_id"])
        for r in retrievals:
            all_dates.add(r["_id"])

        growth_map = {g["_id"]: g for g in growth}
        session_map = {s["_id"]: s for s in session_activity}
        retrieval_map = {r["_id"]: r for r in retrievals}

        timeline = []
        for d in sorted(all_dates):
            g = growth_map.get(d, {})
            s = session_map.get(d, {})
            r = retrieval_map.get(d, {})
            timeline.append({
                "date": d,
                "new_chunks": g.get("new_chunks", 0),
                "avg_quality": round(g.get("avg_quality", 0), 2),
                "sessions": s.get("sessions", 0),
                "session_chunks": s.get("total_chunks", 0),
                "retrievals": r.get("retrievals", 0),
                "helpful": r.get("helpful", 0),
            })

        # Summary stats
        total_chunks = await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": {"$ne": True}})
        total_sessions = await db.agent_training_sessions.count_documents({"agent_id": agent_id})

        return {
            "timeline": timeline,
            "period_days": days,
            "summary": {
                "total_chunks": total_chunks,
                "total_sessions": total_sessions,
                "new_chunks_in_period": sum(g.get("new_chunks", 0) for g in growth),
                "sessions_in_period": sum(s.get("sessions", 0) for s in session_activity),
                "total_retrievals_in_period": sum(r.get("retrievals", 0) for r in retrievals),
            },
        }
