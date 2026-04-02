"""Conversation Learning — Extract knowledge from positive agent interactions.

When users give thumbs-up to agent messages, extract the Q&A pair as a knowledge chunk.
"""
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def extract_knowledge_from_feedback(db, message_id: str, user_id: str):
    """When a user reacts positively to an agent message, extract knowledge from the exchange."""
    msg = await db.messages.find_one({"message_id": message_id}, {"_id": 0})
    if not msg:
        return None

    agent_key = msg.get("agent_key") or msg.get("sender_agent")
    if not agent_key:
        return None

    channel_id = msg.get("channel_id", "")
    workspace_id = msg.get("workspace_id", "")

    # Find the agent
    agent = await db.nexus_agents.find_one(
        {"agent_id": agent_key, "workspace_id": workspace_id}, {"_id": 0, "agent_id": 1, "training": 1}
    )
    if not agent:
        agent = await db.nexus_agents.find_one(
            {"agent_key": agent_key}, {"_id": 0, "agent_id": 1, "workspace_id": 1, "training": 1}
        )
    if not agent:
        return None

    agent_id = agent["agent_id"]
    ws_id = agent.get("workspace_id", workspace_id)

    # Get the preceding user message (the question)
    preceding = await db.messages.find(
        {"channel_id": channel_id, "created_at": {"$lt": msg.get("created_at", "")}},
        {"_id": 0, "content": 1, "sender_id": 1, "agent_key": 1}
    ).sort("created_at", -1).limit(3).to_list(3)

    user_question = ""
    for p in preceding:
        if not p.get("agent_key") and not p.get("sender_agent"):
            user_question = p.get("content", "")
            break

    agent_response = msg.get("content", "")
    if not agent_response or len(agent_response) < 20:
        return None

    # Build the knowledge chunk
    content = agent_response
    if user_question:
        content = f"Q: {user_question}\n\nA: {agent_response}"

    from agent_training_crawler import tokenize_for_retrieval
    tokens = tokenize_for_retrieval(content)

    chunk = {
        "chunk_id": f"kc_{uuid.uuid4().hex[:12]}",
        "agent_id": agent_id,
        "workspace_id": ws_id,
        "session_id": "conversation_learning",
        "content": content,
        "summary": f"Learned from conversation: {content[:120]}",
        "category": "conversation",
        "topic": "Conversation Learning",
        "tags": ["learned", "feedback", "conversation"],
        "source": {
            "type": "conversation",
            "url": "",
            "title": "Chat feedback by user",
            "domain": "",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "message_id": message_id,
            "channel_id": channel_id,
        },
        "tokens": tokens,
        "token_count": len(content.split()),
        "quality_score": 0.85,
        "relevance_score": 0.9,
        "freshness": "current",
        "source_authority": "high",
        "verified_by_human": True,
        "flagged": False,
        "times_retrieved": 0,
        "last_retrieved": None,
        "times_helpful": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Boost quality for Dojo-sourced knowledge (peer-validated data)
    source = chunk.get("source", {})
    if source.get("type") == "dojo_session":
        chunk["quality_score"] = min(1.0, chunk.get("quality_score", 0.5) * 1.2)
        chunk["dojo_validated"] = True

    await db.agent_knowledge.insert_one(chunk)
    chunk.pop("_id", None)

    # Update agent training stats
    await db.nexus_agents.update_one(
        {"agent_id": agent_id},
        {"$inc": {"training.total_chunks": 1}, "$set": {"training.enabled": True}}
    )

    logger.info(f"Conversation learning: extracted chunk {chunk['chunk_id']} from message {message_id}")
    return chunk
