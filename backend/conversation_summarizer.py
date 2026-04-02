"""Conversation Summarization Pipeline — Auto-summarize older messages.

Runs as a background task, summarizing message blocks when channel crosses
a threshold. Summaries stored in channel_summaries collection and injected
into agent context to give awareness of full conversation history.
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

SUMMARY_THRESHOLD = 50
SUMMARY_BLOCK_SIZE = 30


async def summarize_channel_if_needed(db, channel_id: str, workspace_id: str) -> Optional[str]:
    """Check if channel needs summarization and run if threshold met."""
    msg_count = await db.messages.count_documents({"channel_id": channel_id})
    
    # Get count of already-summarized messages
    summary_count = await db.channel_summaries.count_documents({"channel_id": channel_id})
    summarized_msgs = summary_count * SUMMARY_BLOCK_SIZE
    unsummarized = msg_count - summarized_msgs
    
    if unsummarized < SUMMARY_THRESHOLD:
        return None
    
    # Get the oldest unsummarized block
    skip = summarized_msgs
    block = await db.messages.find(
        {"channel_id": channel_id},
        {"_id": 0, "sender_name": 1, "content": 1, "created_at": 1}
    ).sort("created_at", 1).skip(skip).limit(SUMMARY_BLOCK_SIZE).to_list(SUMMARY_BLOCK_SIZE)
    
    if len(block) < SUMMARY_BLOCK_SIZE:
        return None
    
    # Build text to summarize
    text = ""
    for msg in block:
        text += f"[{msg.get('sender_name', '?')}]: {msg.get('content', '')[:500]}\n"
    
    # Generate summary using AI
    summary_text = await _generate_summary(db, workspace_id, text)
    
    if not summary_text:
        return None
    
    summary_id = f"sum_{uuid.uuid4().hex[:12]}"
    summary = {
        "summary_id": summary_id,
        "channel_id": channel_id,
        "workspace_id": workspace_id,
        "block_start": block[0].get("created_at", ""),
        "block_end": block[-1].get("created_at", ""),
        "message_count": len(block),
        "summary": summary_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.channel_summaries.insert_one(summary)
    logger.info(f"Summarized {len(block)} messages in {channel_id}")
    return summary_id


async def _generate_summary(db, workspace_id, conversation_text):
    """Generate a concise summary of a conversation block."""
    try:
        from collaboration_core import get_ai_key_for_agent
        from ai_providers import call_ai_direct
        
        # Try to get any available API key
        for agent in ["chatgpt", "claude", "gemini"]:
            api_key, _ = await get_ai_key_for_agent("system", workspace_id, agent)
            if api_key:
                result = await call_ai_direct(
                    agent, api_key,
                    "You are a conversation summarizer. Create a concise 3-5 sentence summary of the key decisions, actions, and outcomes from this conversation. Focus on what was decided, what was built, and any unresolved items.",
                    f"Summarize this conversation:\n\n{conversation_text[:8000]}",
                    workspace_id=workspace_id, db=db
                )
                return result[:1000]
    except Exception as e:
        logger.debug(f"AI summary failed: {e}")
    
    # Fallback: extractive summary (first and last few messages)
    lines = conversation_text.strip().split("\n")
    if len(lines) > 6:
        return f"Conversation with {len(lines)} messages. Started with: {lines[0][:200]}... Ended with: {lines[-1][:200]}"
    return conversation_text[:500]


async def get_channel_summaries(db, channel_id, limit=5):
    """Get recent summaries for a channel."""
    summaries = await db.channel_summaries.find(
        {"channel_id": channel_id},
        {"_id": 0}
    ).sort("block_end", -1).limit(limit).to_list(limit)
    return summaries


async def build_summary_context(db, channel_id):
    """Build a context string from channel summaries for agent injection."""
    summaries = await get_channel_summaries(db, channel_id, limit=3)
    if not summaries:
        return ""
    
    context = "\n=== CONVERSATION HISTORY SUMMARIES ===\n"
    for s in reversed(summaries):
        context += f"[{s.get('block_start', '?')} to {s.get('block_end', '?')}] ({s.get('message_count', 0)} msgs):\n"
        context += f"  {s['summary']}\n\n"
    context += "=== END SUMMARIES ===\n"
    return context
