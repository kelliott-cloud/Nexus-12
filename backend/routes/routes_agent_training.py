"""Agent Training Module — RAG-based knowledge ingestion and retrieval.

Supports:
- Topic-based web search training (topic → search queries → web → chunks)
- Web page crawling (URL → text → chunks)
- Manual text/document ingestion
- File upload training
- Background task processing with status tracking
- Quality scoring and authority classification
"""

import logging
import re
import uuid
import httpx
from datetime import datetime, timezone, timedelta

from fastapi import Request, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
from nexus_utils import now_iso

logger = logging.getLogger("agent_training")



class TrainURLRequest(BaseModel):
    urls: list
    topics: list = []


class TrainTextRequest(BaseModel):
    title: str = ""
    content: str
    topic: str = "general"


class TrainingTopic(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)
    depth: str = "standard"
    custom_queries: Optional[List[str]] = None


class TopicTrainRequest(BaseModel):
    topics: List[TrainingTopic] = Field(..., min_length=1, max_length=10)
    manual_urls: Optional[List[str]] = None


class TopicSuggestRequest(BaseModel):
    skill_ids: List[str] = []


async def _post_training_enrich(db, agent_id: str, workspace_id: str, session_id: str):
    """Background task: AI-summarize new chunks + compute dense Gemini embeddings + BM25 fallback."""
    try:
        from ai_summarizer import summarize_chunk
        chunks = await db.agent_knowledge.find(
            {"agent_id": agent_id, "workspace_id": workspace_id, "session_id": session_id},
            {"_id": 1, "content": 1, "topic": 1, "summary": 1}
        ).to_list(100)

        for c in chunks:
            text = c.get("content", "")
            old_summary = c.get("summary", "")
            if old_summary and text.startswith(old_summary.rstrip(".")):
                try:
                    new_summary = await summarize_chunk(text, c.get("topic", ""))
                    if new_summary and len(new_summary) > 10:
                        await db.agent_knowledge.update_one(
                            {"_id": c["_id"]},
                            {"$set": {"summary": new_summary, "ai_summarized": True}}
                        )
                except Exception as _e:
                    logger.debug(f"Non-critical: {_e}")
    except Exception as e:
        logger.warning(f"AI summarization enrichment failed: {e}")

    # Dense Gemini embeddings (primary)
    try:
        from gemini_embeddings import compute_and_store_dense_embeddings
        count = await compute_and_store_dense_embeddings(db, agent_id, workspace_id)
        if count > 0:
            logger.info(f"Dense embeddings computed for {count} chunks (agent={agent_id})")
    except Exception as e:
        logger.warning(f"Gemini dense embedding computation failed: {e}")

    # BM25 sparse embeddings (fallback)
    try:
        from ai_embeddings import compute_and_store_embeddings
        await compute_and_store_embeddings(db, agent_id, workspace_id)
    except Exception as e:
        logger.warning(f"BM25 embedding recomputation failed: {e}")


def register_agent_training_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/train/topics")
    async def train_from_topics(
        ws_id: str, agent_id: str, data: TopicTrainRequest,
        request: Request, background_tasks: BackgroundTasks
    ):
        """Start a topic-based training session — searches web, extracts knowledge."""
        user = await get_current_user(request)
        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "name": 1, "skills": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")

        session_id = f"train_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        session = {
            "session_id": session_id,
            "agent_id": agent_id,
            "workspace_id": ws_id,
            "created_by": user["user_id"],
            "status": "pending",
            "source_type": "topics",
            "topics": [
                {"topic": t.topic, "depth": t.depth, "custom_queries": t.custom_queries or [],
                 "status": "pending", "sources_found": 0, "chunks_extracted": 0}
                for t in data.topics
            ],
            "manual_urls": data.manual_urls or [],
            "total_chunks": 0, "total_sources": 0,
            "quality_score": 0, "started_at": None, "completed_at": None,
            "created_at": now, "updated_at": now,
        }
        await db.agent_training_sessions.insert_one(session)
        session.pop("_id", None)

        background_tasks.add_task(
            _run_topic_training, db, session_id, agent_id, ws_id, agent.get("skills") or []
        )
        return session

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/train/suggest-topics")
    async def suggest_training_topics(ws_id: str, agent_id: str, data: TopicSuggestRequest, request: Request):
        """Get suggested training topics based on agent skills."""
        await _authed_user(request, ws_id)
        from agent_training_crawler import get_topic_suggestions
        skill_ids = data.skill_ids
        if not skill_ids:
            agent = await db.nexus_agents.find_one(
                {"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "skills": 1})
            if agent:
                skill_ids = [s.get("skill_id") for s in agent.get("skills") or []]
        suggestions = get_topic_suggestions(skill_ids)
        return {"suggestions": suggestions, "skill_ids": skill_ids}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/train/url")
    async def train_from_url(ws_id: str, agent_id: str, data: TrainURLRequest, request: Request, background_tasks: BackgroundTasks):
        """Crawl URLs and ingest content into agent's knowledge base."""
        user = await _authed_user(request, ws_id)
        from agent_training_crawler import fetch_page_content, chunk_content, score_chunk_quality, classify_source_authority, tokenize_for_retrieval, classify_category, extract_tags, _extract_domain

        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "name": 1, "skills": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")

        session_id = f"train_{uuid.uuid4().hex[:12]}"
        session = {
            "session_id": session_id, "agent_id": agent_id, "workspace_id": ws_id,
            "status": "processing", "source_type": "url", "urls": data.urls, "topics": data.topics,
            "total_chunks": 0, "successful_urls": 0, "failed_urls": [],
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.agent_training_sessions.insert_one(session)
        session.pop("_id", None)

        total_chunks = 0
        successful = 0
        failed = []

        for url in data.urls[:10]:
            page = await fetch_page_content(url)
            if page.get("error"):
                failed.append({"url": url, "error": page["error"]})
                continue

            text = page.get("text", "")
            if len(text) < 50:
                failed.append({"url": url, "error": "Too little content extracted"})
                continue

            chunks = chunk_content(text, page.get("title", ""))
            domain = _extract_domain(url)
            authority = classify_source_authority(domain)
            topic = data.topics[0] if data.topics else "general"

            for chunk_data in chunks:
                quality = await score_chunk_quality(chunk_data["content"], topic, agent.get("skills"))
                if quality < 0.25:
                    continue
                tokens = tokenize_for_retrieval(chunk_data["content"])
                knowledge = {
                    "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                    "agent_id": agent_id, "workspace_id": ws_id, "session_id": session_id,
                    "content": chunk_data["content"], "summary": chunk_data["content"][:200],
                    "category": classify_category(chunk_data["content"]),
                    "topic": topic, "tags": extract_tags(chunk_data["content"], topic),
                    "source": {"type": "web", "url": url, "title": page.get("title", ""), "domain": domain},
                    "tokens": tokens, "token_count": chunk_data.get("token_count", len(tokens)),
                    "quality_score": quality, "source_authority": authority,
                    "flagged": False, "times_retrieved": 0, "created_at": now_iso(),
                }
                await db.agent_knowledge.insert_one(knowledge)
                total_chunks += 1

            successful += 1

        # AI summarization + embedding recomputation
        background_tasks.add_task(_post_training_enrich, db, agent_id, ws_id, session_id)

        await db.agent_training_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "completed", "total_chunks": total_chunks, "successful_urls": successful, "failed_urls": failed, "completed_at": now_iso()}}
        )
        await _update_agent_training_stats(db, agent_id)

        return {"session_id": session_id, "total_chunks": total_chunks, "successful_urls": successful, "failed_urls": failed}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/train/text")
    async def train_from_text(ws_id: str, agent_id: str, data: TrainTextRequest, request: Request, background_tasks: BackgroundTasks):
        """Ingest raw text into agent's knowledge base."""
        user = await _authed_user(request, ws_id)
        from agent_training_crawler import chunk_content, tokenize_for_retrieval, classify_category, extract_tags

        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "name": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")

        session_id = f"train_{uuid.uuid4().hex[:12]}"
        chunks = chunk_content(data.content, data.title)
        total = 0

        for chunk_data in chunks:
            tokens = tokenize_for_retrieval(chunk_data["content"])
            knowledge = {
                "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                "agent_id": agent_id, "workspace_id": ws_id, "session_id": session_id,
                "content": chunk_data["content"], "summary": chunk_data["content"][:200],
                "category": classify_category(chunk_data["content"]),
                "topic": data.topic, "tags": extract_tags(chunk_data["content"], data.topic),
                "source": {"type": "text", "title": data.title},
                "tokens": tokens, "token_count": chunk_data.get("token_count", len(tokens)),
                "quality_score": 0.8, "source_authority": "high",
                "verified_by_human": True, "flagged": False, "times_retrieved": 0, "created_at": now_iso(),
            }
            await db.agent_knowledge.insert_one(knowledge)
            total += 1

        await db.agent_training_sessions.insert_one({
            "session_id": session_id, "agent_id": agent_id, "workspace_id": ws_id,
            "status": "completed", "source_type": "text", "title": data.title,
            "total_chunks": total, "created_by": user["user_id"],
            "created_at": now_iso(), "completed_at": now_iso(),
        })
        await _update_agent_training_stats(db, agent_id)

        # AI summarization + embedding recomputation
        background_tasks.add_task(_post_training_enrich, db, agent_id, ws_id, session_id)

        return {"session_id": session_id, "total_chunks": total}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/train/file")
    async def train_from_file(
        ws_id: str, agent_id: str,
        request: Request, file: UploadFile = File(...), topic: str = Form("general"),
    ):
        """Upload a document (txt/md/csv) and ingest into agent's knowledge base."""
        user = await get_current_user(request)
        from agent_training_crawler import chunk_content, tokenize_for_retrieval, classify_category, extract_tags

        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0, "name": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")

        content_bytes = await file.read()
        try:
            text = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            raise HTTPException(400, "Could not decode file as text")

        if len(text) < 30:
            raise HTTPException(400, "File content is too short")

        session_id = f"train_{uuid.uuid4().hex[:12]}"
        chunks = chunk_content(text, file.filename or "uploaded", max_chunk_size=800)
        total = 0

        for chunk_data in chunks:
            tokens = tokenize_for_retrieval(chunk_data["content"])
            knowledge = {
                "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                "agent_id": agent_id, "workspace_id": ws_id, "session_id": session_id,
                "content": chunk_data["content"], "summary": chunk_data["content"][:200],
                "category": classify_category(chunk_data["content"]),
                "topic": topic, "tags": extract_tags(chunk_data["content"], topic),
                "source": {"type": "file", "title": file.filename or "uploaded", "domain": ""},
                "tokens": tokens, "token_count": chunk_data.get("token_count", len(tokens)),
                "quality_score": 0.85, "source_authority": "high",
                "verified_by_human": False, "flagged": False, "times_retrieved": 0, "created_at": now_iso(),
            }
            await db.agent_knowledge.insert_one(knowledge)
            total += 1

        await db.agent_training_sessions.insert_one({
            "session_id": session_id, "agent_id": agent_id, "workspace_id": ws_id,
            "status": "completed", "source_type": "file", "title": file.filename,
            "total_chunks": total, "created_by": user["user_id"],
            "created_at": now_iso(), "completed_at": now_iso(),
        })
        await _update_agent_training_stats(db, agent_id)
        return {"session_id": session_id, "total_chunks": total, "filename": file.filename}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/train/auto-refresh")
    async def toggle_auto_refresh(ws_id: str, agent_id: str, request: Request):
        """Toggle auto-refresh for agent training (re-crawl stale sources)."""
        await _authed_user(request, ws_id)
        body = await request.json()
        enabled = body.get("enabled", False)
        interval_days = body.get("interval_days", 30)
        await db.nexus_agents.update_one(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"$set": {
                "training.auto_refresh": enabled,
                "training.refresh_interval_days": interval_days,
                "updated_at": now_iso(),
            }}
        )
        return {"auto_refresh": enabled, "interval_days": interval_days}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/train/staleness")
    async def get_knowledge_staleness(ws_id: str, agent_id: str, request: Request, threshold_days: int = 30):
        """Detect stale knowledge chunks that haven't been refreshed beyond threshold."""
        await _authed_user(request, ws_id)
        now = datetime.now(timezone.utc)
        threshold_dt = (now - timedelta(days=threshold_days)).isoformat()

        # Get all active knowledge chunks with their dates
        chunks = await db.agent_knowledge.find(
            {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}},
            {"_id": 0, "chunk_id": 1, "topic": 1, "source": 1, "quality_score": 1,
             "created_at": 1, "last_retrieved": 1, "times_retrieved": 1, "summary": 1}
        ).to_list(500)

        stale = []
        fresh = []
        never_used = []
        for c in chunks:
            created = c.get("created_at", "")
            last_used = c.get("last_retrieved")
            times_used = c.get("times_retrieved", 0)
            is_stale = created < threshold_dt and (not last_used or last_used < threshold_dt)
            if times_used == 0:
                never_used.append(c)
            if is_stale:
                stale.append(c)
            else:
                fresh.append(c)

        # Staleness by topic
        topic_staleness = {}
        for c in chunks:
            t = c.get("topic", "unknown")
            if t not in topic_staleness:
                topic_staleness[t] = {"total": 0, "stale": 0}
            topic_staleness[t]["total"] += 1
            created = c.get("created_at", "")
            last_used = c.get("last_retrieved")
            if created < threshold_dt and (not last_used or last_used < threshold_dt):
                topic_staleness[t]["stale"] += 1

        for t in topic_staleness:
            total = topic_staleness[t]["total"]
            s = topic_staleness[t]["stale"]
            topic_staleness[t]["staleness_pct"] = round(s / max(total, 1) * 100)

        return {
            "agent_id": agent_id,
            "threshold_days": threshold_days,
            "total_chunks": len(chunks),
            "stale_count": len(stale),
            "fresh_count": len(fresh),
            "never_used_count": len(never_used),
            "staleness_pct": round(len(stale) / max(len(chunks), 1) * 100),
            "stale_chunks": stale[:20],
            "never_used_chunks": never_used[:10],
            "topic_staleness": topic_staleness,
        }

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/train/quality-dashboard")
    async def training_quality_dashboard(ws_id: str, agent_id: str, request: Request):
        """Get training quality overview — coverage per skill, gap analysis."""
        await _authed_user(request, ws_id)
        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "skills": 1, "training": 1}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")

        configured_skills = agent.get("skills") or []
        training = agent.get("training") or {}

        # Count chunks per topic
        pipeline = [
            {"$match": {"agent_id": agent_id, "flagged": {"$ne": True}}},
            {"$group": {"_id": "$topic", "count": {"$sum": 1}, "avg_quality": {"$avg": "$quality_score"}}},
        ]
        topic_counts = {r["_id"]: {"count": r["count"], "avg_quality": round(r.get("avg_quality") or 0, 2)}
                        for r in await db.agent_knowledge.aggregate(pipeline).to_list(50)}

        # Build per-skill coverage from the crawler suggestions
        from agent_training_crawler import SKILL_TOPIC_SUGGESTIONS
        skill_coverage = []
        for skill_cfg in configured_skills:
            sid = skill_cfg.get("skill_id", "")
            suggested = SKILL_TOPIC_SUGGESTIONS.get(sid, [])
            covered_topics = [t for t in suggested if t in topic_counts]
            chunk_total = sum(topic_counts[t]["count"] for t in covered_topics)
            avg_q = sum(topic_counts[t]["avg_quality"] for t in covered_topics) / max(len(covered_topics), 1) if covered_topics else 0
            skill_coverage.append({
                "skill_id": sid,
                "level": skill_cfg.get("level", "novice"),
                "suggested_topics": suggested,
                "covered_topics": covered_topics,
                "uncovered_topics": [t for t in suggested if t not in topic_counts],
                "chunk_count": chunk_total,
                "avg_quality": round(avg_q, 2),
                "coverage_pct": round(len(covered_topics) / max(len(suggested), 1) * 100),
            })

        total_chunks = await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": {"$ne": True}})
        return {
            "agent_id": agent_id,
            "total_chunks": total_chunks,
            "training_enabled": training.get("enabled", False),
            "auto_refresh": training.get("auto_refresh", False),
            "skill_coverage": skill_coverage,
            "topic_breakdown": topic_counts,
        }

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/knowledge")
    async def get_agent_knowledge(ws_id: str, agent_id: str, request: Request, topic: str = None, category: str = None, q: str = None, limit: int = 50):
        """List agent's knowledge chunks with search and filters."""
        await _authed_user(request, ws_id)
        query_filter = {"agent_id": agent_id, "workspace_id": ws_id}
        if topic:
            query_filter["topic"] = topic
        if category:
            query_filter["category"] = category
        if q:
            from nexus_utils import now_iso, safe_regex
            query_filter["content"] = {"$regex": safe_regex(q), "$options": "i"}
        chunks = await db.agent_knowledge.find(query_filter, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        topics = await db.agent_knowledge.distinct("topic", {"agent_id": agent_id, "workspace_id": ws_id})
        total = await db.agent_knowledge.count_documents({"agent_id": agent_id, "workspace_id": ws_id})
        return {"chunks": chunks, "topics": topics, "total": total}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/knowledge/stats")
    async def get_knowledge_stats(ws_id: str, agent_id: str, request: Request):
        """Get summary stats for an agent's knowledge corpus."""
        await _authed_user(request, ws_id)
        total = await db.agent_knowledge.count_documents({"agent_id": agent_id})
        flagged = await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": True})
        pipeline = [
            {"$match": {"agent_id": agent_id, "flagged": {"$ne": True}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}, "avg_quality": {"$avg": "$quality_score"}}},
        ]
        categories = await db.agent_knowledge.aggregate(pipeline).to_list(20)
        source_pipeline = [
            {"$match": {"agent_id": agent_id, "flagged": {"$ne": True}}},
            {"$group": {"_id": "$source.domain", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 10},
        ]
        sources = await db.agent_knowledge.aggregate(source_pipeline).to_list(10)
        most_used = await db.agent_knowledge.find(
            {"agent_id": agent_id, "times_retrieved": {"$gt": 0}},
            {"_id": 0, "chunk_id": 1, "summary": 1, "times_retrieved": 1}
        ).sort("times_retrieved", -1).limit(10).to_list(10)
        return {
            "total_chunks": total, "flagged": flagged, "active": total - flagged,
            "categories": {c["_id"]: {"count": c["count"], "avg_quality": round(c.get("avg_quality") or 0, 2)} for c in categories},
            "top_sources": [{"domain": s["_id"], "count": s["count"]} for s in sources],
            "most_retrieved": most_used,
        }

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/training-sessions")
    async def get_training_sessions(ws_id: str, agent_id: str, request: Request):
        """List training sessions for an agent."""
        await _authed_user(request, ws_id)
        sessions = await db.agent_training_sessions.find(
            {"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return sessions

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/training-sessions/{session_id}")
    async def get_training_session_detail(ws_id: str, agent_id: str, session_id: str, request: Request):
        """Get detailed info for a single training session."""
        await _authed_user(request, ws_id)
        session = await db.agent_training_sessions.find_one(
            {"session_id": session_id, "agent_id": agent_id}, {"_id": 0}
        )
        if not session:
            raise HTTPException(404, "Training session not found")
        return session

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/training-sessions/{session_id}/progress")
    async def get_training_progress(ws_id: str, agent_id: str, session_id: str, request: Request):
        """Get real-time training progress (poll-based alternative to WebSocket)."""
        await _authed_user(request, ws_id)
        from routes.routes_training_ws import get_training_progress as _get_progress
        progress = _get_progress(session_id)
        if progress:
            return progress
        session = await db.agent_training_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "status": 1, "total_chunks": 1, "topics": 1}
        )
        if session:
            return {"session_id": session_id, "status": session.get("status", "unknown"), "total_chunks": session.get("total_chunks", 0)}
        return {"session_id": session_id, "status": "unknown"}

    @api_router.delete("/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}")
    async def delete_knowledge_chunk(ws_id: str, agent_id: str, chunk_id: str, request: Request):
        """Delete a specific knowledge chunk."""
        await _authed_user(request, ws_id)
        result = await db.agent_knowledge.delete_one({"chunk_id": chunk_id, "agent_id": agent_id, "workspace_id": ws_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Chunk not found")
        return {"deleted": chunk_id}

    @api_router.put("/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}")
    async def edit_knowledge_chunk(ws_id: str, agent_id: str, chunk_id: str, request: Request):
        """Edit a knowledge chunk's content, category, or tags."""
        await _authed_user(request, ws_id)
        body = await request.json()
        updates = {"updated_at": now_iso()}
        if "content" in body and body["content"].strip():
            from agent_training_crawler import tokenize_for_retrieval
            updates["content"] = body["content"].strip()
            updates["tokens"] = tokenize_for_retrieval(updates["content"])
            updates["token_count"] = len(updates["content"].split())
            updates["summary"] = updates["content"][:200]
        if "category" in body:
            updates["category"] = body["category"]
        if "tags" in body:
            updates["tags"] = body["tags"]
        if "topic" in body:
            updates["topic"] = body["topic"]
        result = await db.agent_knowledge.update_one(
            {"chunk_id": chunk_id, "agent_id": agent_id, "workspace_id": ws_id},
            {"$set": updates}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Chunk not found")
        updated = await db.agent_knowledge.find_one({"chunk_id": chunk_id}, {"_id": 0})
        return updated

    @api_router.put("/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}/flag")
    async def flag_knowledge_chunk(ws_id: str, agent_id: str, chunk_id: str, request: Request):
        """Flag a knowledge chunk as inaccurate (excluded from retrieval)."""
        await _authed_user(request, ws_id)
        await db.agent_knowledge.update_one(
            {"chunk_id": chunk_id, "agent_id": agent_id},
            {"$set": {"flagged": True, "updated_at": now_iso()}}
        )
        return {"flagged": chunk_id}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/knowledge/query")
    async def query_agent_knowledge(ws_id: str, agent_id: str, request: Request):
        """Retrieve relevant knowledge chunks for a query using TF-IDF similarity."""
        await _authed_user(request, ws_id)
        body = await request.json()
        query_text = body.get("query", "")
        top_k = body.get("top_k", 5)
        if not query_text:
            raise HTTPException(400, "Query text required")
        chunks = await db.agent_knowledge.find(
            {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}},
            {"_id": 0, "chunk_id": 1, "content": 1, "topic": 1, "source": 1, "tokens": 1}
        ).limit(500).to_list(500)
        if not chunks:
            return {"results": [], "total_searched": 0}
        from semantic_memory import _compute_tfidf, _cosine_sim
        documents = [c["content"] for c in chunks]
        all_docs = documents + [query_text]
        vectors, vocab_idx = _compute_tfidf(all_docs)
        query_vec = vectors[-1]
        scored = []
        for i, dv in enumerate(vectors[:-1]):
            score = _cosine_sim(query_vec, dv)
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scored[:top_k]:
            chunk = chunks[idx]
            chunk["relevance_score"] = round(score, 4)
            results.append(chunk)
            await db.agent_knowledge.update_one(
                {"chunk_id": chunk["chunk_id"]}, {"$inc": {"times_retrieved": 1}}
            )
        return {"results": results, "total_searched": len(chunks)}


async def _run_topic_training(db, session_id, agent_id, workspace_id, agent_skills):
    """Background task: full topic-based training pipeline."""
    from agent_training_crawler import (
        generate_search_queries, search_web, fetch_page_content,
        chunk_content, score_chunk_quality, tokenize_for_retrieval,
        classify_source_authority, classify_category, extract_tags,
        _extract_domain, DEPTH_LIMITS
    )

    start = datetime.now(timezone.utc)
    await db.agent_training_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"status": "crawling", "started_at": start.isoformat()}}
    )

    # Training progress WS notifications
    try:
        from routes_training_ws import update_training_progress
    except ImportError as e:
        logger.error(f"Failed to import training WS module: {e}")
        def update_training_progress(*a, **k):
            logger.warning("update_training_progress called but WS module unavailable")

    update_training_progress(session_id, {"status": "crawling", "progress_pct": 0, "agent_id": agent_id})
    session = await db.agent_training_sessions.find_one({"session_id": session_id}, {"_id": 0})
    total_chunks = 0
    total_sources = 0
    all_quality_scores = []

    try:
        for i, topic_config in enumerate(session.get("topics") or []):
            topic = topic_config["topic"]
            depth = topic_config.get("depth", "standard")
            total_topics = len(session.get("topics") or [])
            update_training_progress(session_id, {
                "status": "crawling", "agent_id": agent_id,
                "progress_pct": int(i / max(total_topics, 1) * 80),
                "current_topic": topic, "topic_index": i, "total_topics": total_topics,
                "total_chunks": total_chunks,
            })
            max_sources = DEPTH_LIMITS.get(depth, 8)
            queries = topic_config.get("custom_queries") or []
            if not queries:
                queries = await generate_search_queries(topic, agent_skills)
                await db.agent_training_sessions.update_one(
                    {"session_id": session_id},
                    {"$set": {f"topics.{i}.custom_queries": queries}}
                )

            all_results = []
            seen_urls = set()
            for query in queries:
                results = await search_web(db, query, num_results=5)
                for r in results:
                    if r.get("url") and r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)
                        if len(all_results) >= max_sources:
                            break
                if len(all_results) >= max_sources:
                    break

            await db.agent_training_sessions.update_one(
                {"session_id": session_id},
                {"$set": {f"topics.{i}.status": "extracting", f"topics.{i}.sources_found": len(all_results), "status": "extracting"}}
            )

            topic_chunks = 0
            for result in all_results:
                page = await fetch_page_content(result["url"])
                if page.get("error"):
                    continue
                total_sources += 1
                text = page.get("text", "")
                if len(text) < 100:
                    continue
                chunks = chunk_content(text, page.get("title", ""), max_chunk_size=800)
                authority = classify_source_authority(result.get("domain", ""))

                for chunk_data in chunks:
                    quality = await score_chunk_quality(chunk_data["content"], topic, agent_skills)
                    if quality < 0.3:
                        continue
                    tokens = tokenize_for_retrieval(chunk_data["content"])
                    entry = {
                        "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                        "agent_id": agent_id, "workspace_id": workspace_id, "session_id": session_id,
                        "content": chunk_data["content"], "summary": chunk_data["content"][:200],
                        "category": classify_category(chunk_data["content"]),
                        "topic": topic, "tags": extract_tags(chunk_data["content"], topic),
                        "source": {"type": "web", "url": result["url"], "title": page.get("title", result.get("title", "")), "domain": result.get("domain", "")},
                        "tokens": tokens, "token_count": chunk_data.get("token_count", len(tokens)),
                        "quality_score": quality, "source_authority": authority,
                        "flagged": False, "times_retrieved": 0, "created_at": now_iso(),
                    }
                    await db.agent_knowledge.insert_one(entry)
                    total_chunks += 1
                    topic_chunks += 1
                    all_quality_scores.append(quality)

            await db.agent_training_sessions.update_one(
                {"session_id": session_id},
                {"$set": {f"topics.{i}.status": "completed", f"topics.{i}.chunks_extracted": topic_chunks}}
            )

        # Process manual URLs
        for url in session.get("manual_urls") or []:
            page = await fetch_page_content(url)
            if page.get("error"):
                continue
            total_sources += 1
            chunks = chunk_content(page.get("text", ""), page.get("title", ""))
            authority = classify_source_authority(_extract_domain(url))
            for chunk_data in chunks:
                quality = await score_chunk_quality(chunk_data["content"], "manual", agent_skills)
                if quality < 0.25:
                    continue
                tokens = tokenize_for_retrieval(chunk_data["content"])
                entry = {
                    "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                    "agent_id": agent_id, "workspace_id": workspace_id, "session_id": session_id,
                    "content": chunk_data["content"], "summary": chunk_data["content"][:200],
                    "category": classify_category(chunk_data["content"]),
                    "topic": "Manual URL", "tags": [],
                    "source": {"type": "web", "url": url, "title": page.get("title", ""), "domain": _extract_domain(url)},
                    "tokens": tokens, "token_count": chunk_data.get("token_count", 0),
                    "quality_score": quality, "source_authority": authority,
                    "flagged": False, "times_retrieved": 0, "created_at": now_iso(),
                }
                await db.agent_knowledge.insert_one(entry)
                total_chunks += 1
                all_quality_scores.append(quality)

        end = datetime.now(timezone.utc)
        avg_quality = round(sum(all_quality_scores) / max(len(all_quality_scores), 1) * 100, 1) if all_quality_scores else 0

        await db.agent_training_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed", "total_sources": total_sources, "total_chunks": total_chunks,
                "quality_score": avg_quality, "completed_at": end.isoformat(),
                "duration_seconds": int((end - start).total_seconds()), "updated_at": end.isoformat(),
            }}
        )
        await _update_agent_training_stats(db, agent_id)
        logger.info(f"Training session {session_id} completed: {total_chunks} chunks from {total_sources} sources")

    except Exception as e:
        logger.error(f"Training session {session_id} failed: {e}")
        await db.agent_training_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "failed", "error": str(e), "updated_at": now_iso()}}
        )


async def _update_agent_training_stats(db, agent_id):
    """Update agent's training stats after a training session."""
    total_chunks = await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": {"$ne": True}})
    total_sessions = await db.agent_training_sessions.count_documents({"agent_id": agent_id})
    await db.nexus_agents.update_one(
        {"agent_id": agent_id},
        {"$set": {
            "training.enabled": True,
            "training.total_chunks": total_chunks,
            "training.total_sessions": total_sessions,
            "training.last_trained": now_iso(),
            "updated_at": now_iso(),
        }}
    )
