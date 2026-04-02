"""Auto-Refresh Training — Background scheduler to re-crawl stale knowledge sources.

Checks agents with auto_refresh enabled and re-crawls URLs that are past their freshness threshold.
Integrates with the existing APScheduler infrastructure.
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Request

logger = logging.getLogger(__name__)


async def run_training_refresh(db):
    """Check all agents with auto_refresh enabled and re-crawl stale sources."""
    now = datetime.now(timezone.utc)

    agents = await db.nexus_agents.find(
        {"training.auto_refresh": True, "training.enabled": True},
        {"_id": 0, "agent_id": 1, "workspace_id": 1, "training": 1, "skills": 1}
    ).to_list(50)

    if not agents:
        return

    for agent in agents:
        agent_id = agent["agent_id"]
        ws_id = agent["workspace_id"]
        training = agent.get("training") or {}
        refresh_days = training.get("refresh_interval_days", 30)
        last_trained = training.get("last_trained")

        if last_trained:
            try:
                last_dt = datetime.fromisoformat(last_trained.replace("Z", "+00:00"))
                if (now - last_dt).days < refresh_days:
                    continue
            except Exception as e:
                logger.warning(f"Non-critical error at line 37: {e}")

        # Find stale knowledge sources to re-crawl
        stale_cutoff = (now - timedelta(days=refresh_days)).isoformat()
        stale_chunks = await db.agent_knowledge.find(
            {
                "agent_id": agent_id,
                "source.type": "web",
                "source.crawled_at": {"$lt": stale_cutoff},
                "flagged": {"$ne": True},
            },
            {"_id": 0, "source.url": 1}
        ).to_list(50)

        urls_to_recrawl = list({(c.get("source") or {}).get("url", "") for c in stale_chunks if (c.get("source") or {}).get("url")})

        if not urls_to_recrawl:
            continue

        logger.info(f"Auto-refresh: re-crawling {len(urls_to_recrawl)} URLs for agent {agent_id}")

        try:
            from agent_training_crawler import fetch_page_content, chunk_content, \
                score_chunk_quality, tokenize_for_retrieval, classify_source_authority
            import uuid

            refreshed = 0
            for url in urls_to_recrawl[:10]:
                page = await fetch_page_content(url)
                if page.get("error"):
                    continue

                text = page.get("text", "")
                if len(text) < 100:
                    continue

                chunks = chunk_content(text, page.get("title", ""), max_chunk_size=800)
                domain = page.get("domain", "")
                authority = classify_source_authority(domain)

                for chunk_data in chunks[:5]:
                    quality = await score_chunk_quality(chunk_data["content"], "refresh", agent.get("skills") or [])
                    if quality < 0.35:
                        continue

                    tokens = tokenize_for_retrieval(chunk_data["content"])
                    entry = {
                        "chunk_id": f"kc_{uuid.uuid4().hex[:12]}",
                        "agent_id": agent_id,
                        "workspace_id": ws_id,
                        "session_id": "auto_refresh",
                        "content": chunk_data["content"],
                        "summary": chunk_data["content"][:200],
                        "category": "concept",
                        "topic": "Auto-Refreshed",
                        "tags": ["auto-refresh"],
                        "source": {
                            "type": "web",
                            "url": url,
                            "title": page.get("title", ""),
                            "domain": domain,
                            "crawled_at": now.isoformat(),
                        },
                        "tokens": tokens,
                        "token_count": chunk_data.get("token_count", 0),
                        "quality_score": quality,
                        "relevance_score": quality,
                        "freshness": "current",
                        "source_authority": authority,
                        "verified_by_human": False,
                        "flagged": False,
                        "times_retrieved": 0,
                        "last_retrieved": None,
                        "times_helpful": 0,
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                    }
                    await db.agent_knowledge.insert_one(entry)
                    refreshed += 1

            # Mark old chunks as stale
            await db.agent_knowledge.update_many(
                {"agent_id": agent_id, "source.url": {"$in": urls_to_recrawl}, "source.crawled_at": {"$lt": stale_cutoff}},
                {"$set": {"freshness": "stale"}}
            )

            # Update agent
            await db.nexus_agents.update_one(
                {"agent_id": agent_id},
                {"$set": {
                    "training.last_trained": now.isoformat(),
                    "training.total_chunks": await db.agent_knowledge.count_documents({"agent_id": agent_id, "flagged": {"$ne": True}}),
                }}
            )

            logger.info(f"Auto-refresh: agent {agent_id} refreshed {refreshed} chunks from {len(urls_to_recrawl)} URLs")

        except Exception as e:
            logger.error(f"Auto-refresh failed for agent {agent_id}: {e}")


def register_auto_refresh_routes(api_router, db, get_current_user):
    """Routes to manage auto-refresh settings per agent."""

    @api_router.put("/workspaces/{ws_id}/agents/{agent_id}/training/auto-refresh")
    async def set_auto_refresh(ws_id: str, agent_id: str, request: Request):
        """Toggle auto-refresh and set interval."""
        await get_current_user(request)
        body = await request.json()
        enabled = body.get("enabled", False)
        interval_days = max(1, min(body.get("interval_days", 30), 365))

        await db.nexus_agents.update_one(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"$set": {
                "training.auto_refresh": enabled,
                "training.refresh_interval_days": interval_days,
            }}
        )
        return {"auto_refresh": enabled, "interval_days": interval_days}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/training/auto-refresh")
    async def get_auto_refresh(ws_id: str, agent_id: str, request: Request):
        """Get auto-refresh settings for an agent."""
        await get_current_user(request)
        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "training.auto_refresh": 1, "training.refresh_interval_days": 1, "training.last_trained": 1}
        )
        t = (agent or {}).get("training") or {}
        return {
            "auto_refresh": t.get("auto_refresh", False),
            "interval_days": t.get("refresh_interval_days", 30),
            "last_trained": t.get("last_trained"),
        }
