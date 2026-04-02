from nexus_utils import now_iso
"""Cross-Workspace Agent Leaderboard + Knowledge Deduplication & Quality Scoring.

- Global leaderboard: ranks agents across all workspaces by skill, evaluation, usage.
- Knowledge dedup: detects near-duplicate chunks via Jaccard similarity.
- Quality scoring: rates chunks on length, structure, keyword density.
"""

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from typing import Optional

logger = logging.getLogger("agent_leaderboard")



def _jaccard_similarity(a, b):
    """Token-level Jaccard similarity between two strings."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0
    return len(set_a & set_b) / len(set_a | set_b)


def _compute_quality_score(content):
    """Score a knowledge chunk 0-100 based on quality heuristics."""
    if not content:
        return 0
    words = content.split()
    word_count = len(words)
    sentences = re.split(r'[.!?]+', content)
    sentence_count = len([s for s in sentences if s.strip()])

    score = 0
    # Length score (0-30): optimal 100-500 words
    if word_count < 20:
        score += 5
    elif word_count < 50:
        score += 15
    elif word_count <= 500:
        score += 30
    elif word_count <= 1000:
        score += 25
    else:
        score += 15

    # Structure score (0-25): has sentences, paragraphs
    if sentence_count >= 3:
        score += 15
    elif sentence_count >= 1:
        score += 8
    if "\n" in content:
        score += 10

    # Information density (0-25): unique words ratio
    unique_ratio = len(set(words)) / max(word_count, 1)
    score += int(unique_ratio * 25)

    # Technical content bonus (0-20)
    tech_markers = ["```", "http", "function", "class", "def ", "import ", "config", "api", "database"]
    tech_hits = sum(1 for m in tech_markers if m in content.lower())
    score += min(20, tech_hits * 5)

    return min(100, score)


def register_leaderboard_routes(api_router, db, get_current_user):

    @api_router.get("/leaderboard/agents")
    async def global_agent_leaderboard(request: Request, metric: str = "evaluation", limit: int = 20):
        """Cross-workspace agent leaderboard ranked by various metrics."""
        user = await get_current_user(request)

        if metric == "evaluation":
            pipeline = [
                {"$match": {"evaluation.overall_score": {"$gt": 0}}},
                {"$project": {
                    "_id": 0, "agent_id": 1, "name": 1, "workspace_id": 1,
                    "base_model": 1, "color": 1,
                    "score": "$evaluation.overall_score",
                    "badges": "$evaluation.badges",
                    "skills_count": {"$size": {"$ifNull": ["$skills", []]}},
                }},
                {"$sort": {"score": -1}},
                {"$limit": limit},
            ]
        elif metric == "skills":
            pipeline = [
                {"$project": {
                    "_id": 0, "agent_id": 1, "name": 1, "workspace_id": 1,
                    "base_model": 1, "color": 1,
                    "skills_count": {"$size": {"$ifNull": ["$skills", []]}},
                    "score": {"$size": {"$ifNull": ["$skills", []]}},
                }},
                {"$match": {"score": {"$gt": 0}}},
                {"$sort": {"score": -1}},
                {"$limit": limit},
            ]
        elif metric == "messages":
            pipeline = [
                {"$match": {"stats.total_messages": {"$gt": 0}}},
                {"$project": {
                    "_id": 0, "agent_id": 1, "name": 1, "workspace_id": 1,
                    "base_model": 1, "color": 1,
                    "score": "$stats.total_messages",
                    "skills_count": {"$size": {"$ifNull": ["$skills", []]}},
                }},
                {"$sort": {"score": -1}},
                {"$limit": limit},
            ]
        else:
            pipeline = [
                {"$project": {
                    "_id": 0, "agent_id": 1, "name": 1, "workspace_id": 1,
                    "base_model": 1, "color": 1,
                    "score": {"$ifNull": ["$evaluation.overall_score", 0]},
                    "skills_count": {"$size": {"$ifNull": ["$skills", []]}},
                }},
                {"$sort": {"score": -1}},
                {"$limit": limit},
            ]

        agents = []
        async for doc in db.nexus_agents.aggregate(pipeline):
            doc["rank"] = len(agents) + 1
            agents.append(doc)

        return {"leaderboard": agents, "metric": metric, "total": len(agents)}

    @api_router.get("/leaderboard/skills")
    async def global_skill_leaderboard(request: Request, limit: int = 30):
        """Cross-workspace skill proficiency leaderboard."""
        user = await get_current_user(request)

        pipeline = [
            {"$match": {"proficiency": {"$gt": 0}}},
            {"$sort": {"proficiency": -1}},
            {"$limit": limit},
            {"$project": {
                "_id": 0, "agent_key": 1, "workspace_id": 1,
                "skill": 1, "level": 1, "proficiency": 1,
                "xp": 1, "streak": 1, "best_streak": 1,
            }},
        ]

        records = []
        async for doc in db.agent_skills.aggregate(pipeline):
            doc["rank"] = len(records) + 1
            records.append(doc)

        return {"leaderboard": records, "total": len(records)}


def register_knowledge_quality_routes(api_router, db, get_current_user):

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/knowledge/deduplicate")
    async def deduplicate_knowledge(ws_id: str, agent_id: str, request: Request, threshold: float = 0.7):
        """Find and optionally remove near-duplicate knowledge chunks."""
        user = await get_current_user(request)

        chunks = await db.agent_knowledge.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "chunk_id": 1, "content": 1, "quality_score": 1}
        ).limit(500).to_list(500)

        if len(chunks) < 2:
            return {"duplicates": [], "total_checked": len(chunks)}

        # Find duplicates using Jaccard similarity
        duplicates = []
        seen = set()
        for i in range(len(chunks)):
            if chunks[i]["chunk_id"] in seen:
                continue
            for j in range(i + 1, len(chunks)):
                if chunks[j]["chunk_id"] in seen:
                    continue
                sim = _jaccard_similarity(chunks[i]["content"], chunks[j]["content"])
                if sim >= threshold:
                    # Keep the one with higher quality score
                    qi = chunks[i].get("quality_score", 0)
                    qj = chunks[j].get("quality_score", 0)
                    remove_id = chunks[j]["chunk_id"] if qi >= qj else chunks[i]["chunk_id"]
                    keep_id = chunks[i]["chunk_id"] if qi >= qj else chunks[j]["chunk_id"]
                    duplicates.append({
                        "keep": keep_id,
                        "remove": remove_id,
                        "similarity": round(sim, 3),
                    })
                    seen.add(remove_id)

        return {
            "duplicates": duplicates,
            "total_checked": len(chunks),
            "duplicate_count": len(duplicates),
        }

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/knowledge/deduplicate/apply")
    async def apply_deduplication(ws_id: str, agent_id: str, request: Request):
        """Remove detected duplicate chunks."""
        user = await get_current_user(request)
        body = await request.json()
        chunk_ids_to_remove = body.get("chunk_ids") or []

        if not chunk_ids_to_remove:
            return {"removed": 0}

        result = await db.agent_knowledge.delete_many({
            "chunk_id": {"$in": chunk_ids_to_remove},
            "agent_id": agent_id,
            "workspace_id": ws_id,
        })
        return {"removed": result.deleted_count}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/knowledge/rescore")
    async def rescore_knowledge(ws_id: str, agent_id: str, request: Request):
        """Recompute quality scores for all knowledge chunks."""
        user = await get_current_user(request)

        chunks = await db.agent_knowledge.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "chunk_id": 1, "content": 1}
        ).limit(500).to_list(500)

        updated = 0
        for chunk in chunks:
            score = _compute_quality_score(chunk["content"])
            await db.agent_knowledge.update_one(
                {"chunk_id": chunk["chunk_id"]},
                {"$set": {"quality_score": score}}
            )
            updated += 1

        return {"rescored": updated}

    @api_router.get("/leaderboard/snapshots")
    async def get_leaderboard_snapshots(request: Request, days: int = 30, limit: int = 10):
        """Get historical leaderboard snapshots for trend analysis."""
        await get_current_user(request)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        snapshots = await db.leaderboard_snapshots.find(
            {"timestamp": {"$gte": since}}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"snapshots": snapshots, "period_days": days}

    @api_router.post("/leaderboard/snapshot")
    async def create_leaderboard_snapshot(request: Request):
        """Capture a leaderboard snapshot for trend tracking."""
        await get_current_user(request)
        agents = await db.nexus_agents.find(
            {}, {"_id": 0, "agent_id": 1, "name": 1, "evaluation.overall_score": 1, "stats.total_messages": 1, "base_model": 1, "workspace_id": 1}
        ).limit(100).to_list(100)
        ranked = sorted(agents, key=lambda a: (a.get("evaluation") or {}).get("overall_score", 0), reverse=True)
        snapshot_data = []
        for i, a in enumerate(ranked[:25]):
            snapshot_data.append({
                "rank": i + 1,
                "agent_id": a.get("agent_id"),
                "name": a.get("name"),
                "score": (a.get("evaluation") or {}).get("overall_score", 0),
                "messages": (a.get("stats") or {}).get("total_messages", 0),
                "base_model": a.get("base_model"),
                "workspace_id": a.get("workspace_id"),
            })
        snapshot = {
            "snapshot_id": f"lbs_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": snapshot_data,
            "total_agents": len(agents),
        }
        await db.leaderboard_snapshots.insert_one(snapshot)
        snapshot.pop("_id", None)
        return snapshot
