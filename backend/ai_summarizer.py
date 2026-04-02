"""AI Summarizer — Uses Anthropic Claude for chunk summarization via direct API calls."""
import os
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def summarize_chunk(text: str, topic: str = "", db=None) -> str:
    """Generate a concise summary of a knowledge chunk using Claude."""
    try:
        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "ANTHROPIC_API_KEY") if db else None
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return text[:200]

        prompt = "Summarize this knowledge chunk in 1-2 sentences (max 80 words)."
        if topic:
            prompt += f" Topic context: {topic}."
        prompt += f"\n\nText:\n{text[:2000]}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5-20250929", "max_tokens": 200,
                      "system": "You are a concise summarizer. Output ONLY the summary, no preamble.",
                      "messages": [{"role": "user", "content": prompt}]})
            if resp.status_code == 200:
                result = resp.json().get("content", [{}])[0].get("text", "")
                return result.strip() if result else text[:200]
            else:
                logger.warning(f"Anthropic summarize returned {resp.status_code}")
                return text[:200]
    except Exception as e:
        logger.warning(f"AI summarization failed, using fallback: {e}")
        return text[:200]


async def summarize_chunks_batch(chunks: list, topic: str = "", db=None) -> list:
    """Summarize multiple chunks. Returns list of summaries in same order."""
    summaries = []
    for chunk in chunks:
        s = await summarize_chunk(chunk, topic, db=db)
        summaries.append(s)
    return summaries
