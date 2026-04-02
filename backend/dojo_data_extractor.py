"""Dojo Data Extractor — Parse session transcripts into training data.

Converts completed Dojo role-play transcripts into structured Q&A
pairs suitable for ingestion into the existing agent_knowledge collection.
Integrates with:
  - agent_training_crawler.py (tokenization, quality scoring)
  - gemini_embeddings.py (dense vector computation)
  - conversation_learning.py (same ingestion schema)
"""
import uuid
import logging
import re
from datetime import datetime, timezone

from nexus_utils import now_iso

logger = logging.getLogger("dojo_data_extractor")


async def extract_training_data(db, session_id):
    """Extract Q&A pairs from a completed Dojo session transcript."""
    session = await db.dojo_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session or session.get("status") != "completed":
        return None

    turns = session.get("turns") or []
    if len(turns) < 2:
        return None

    workspace_id = session.get("workspace_id", "")
    task = session.get("task") or {}
    topic = task.get("domain", "general")
    pairs = []

    # Strategy 1: Consecutive turn pairs (driver asks, executor answers)
    for i in range(len(turns) - 1):
        t_a, t_b = turns[i], turns[i + 1]
        if t_a.get("agent_id") == t_b.get("agent_id"):
            continue  # Skip monologue turns

        q = _clean_markers(t_a.get("content", ""))
        a = _clean_markers(t_b.get("content", ""))
        if len(q) < 30 or len(a) < 50:
            continue

        quality = _score_pair_quality(q, a, t_b)
        pairs.append({
            "question": q, "answer": a, "topic": topic,
            "quality_score": quality,
            "source_turns": [t_a.get("turn_number"), t_b.get("turn_number")],
            "roles": [t_a.get("role", ""), t_b.get("role", "")],
        })

    # Strategy 2: Extract code blocks as standalone knowledge chunks
    for t in turns:
        content = t.get("content", "")
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', content, re.DOTALL)
        for lang, code in code_blocks:
            if len(code.strip()) < 50:
                continue
            lang = lang or "python"
            idx = t.get("turn_number", 0)
            preceding = ""
            if idx > 0 and idx - 1 < len(turns):
                preceding = _clean_markers(turns[idx - 1].get("content", ""))[:300]

            pairs.append({
                "question": f"Write {lang} code: {preceding}" if preceding
                            else f"Provide {lang} implementation",
                "answer": f"```{lang}\n{code.strip()}\n```",
                "topic": f"code_{lang}",
                "quality_score": min(0.9, 0.5 + len(code.strip()) / 2000),
                "source_turns": [idx],
                "roles": [t.get("role", "")],
            })

    if not pairs:
        return None

    # Store extraction record
    extraction_id = f"dojo_ext_{uuid.uuid4().hex[:12]}"
    avg_quality = sum(p["quality_score"] for p in pairs) / len(pairs)

    # Target agent = first non-driver agent
    target_agent = ""
    for a in (session.get("agents") or []):
        if not a.get("is_driver", False):
            target_agent = a["agent_id"]
            break
    if not target_agent and session.get("agents"):
        target_agent = session["agents"][0]["agent_id"]

    auto_approve_threshold = 0.8
    status = "approved" if avg_quality >= auto_approve_threshold else "pending"

    extraction = {
        "extraction_id": extraction_id, "session_id": session_id,
        "workspace_id": workspace_id, "agent_id": target_agent,
        "pairs": pairs, "pair_count": len(pairs),
        "avg_quality": round(avg_quality, 3), "status": status,
        "ingested_chunk_ids": [], "created_at": now_iso(),
    }
    await db.dojo_extracted_data.insert_one(extraction)

    # Update session with extraction stats
    await db.dojo_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"synthetic_data": {
            "extraction_id": extraction_id,
            "pairs_extracted": len(pairs),
            "quality_avg": round(avg_quality, 3),
            "status": status,
        }}},
    )

    # Auto-ingest if quality is high enough
    if status == "approved":
        await ingest_extracted_data(db, extraction_id)

    return extraction_id


async def ingest_extracted_data(db, extraction_id):
    """Ingest approved extracted data into agent_knowledge.
    Uses the same schema as conversation_learning.py for consistency.
    """
    ext = await db.dojo_extracted_data.find_one(
        {"extraction_id": extraction_id}, {"_id": 0}
    )
    if not ext or ext.get("status") not in ("approved", "pending"):
        return

    from agent_training_crawler import tokenize_for_retrieval

    chunk_ids = []
    for pair in ext.get("pairs") or []:
        chunk_id = f"dojo_k_{uuid.uuid4().hex[:12]}"
        content = f"Q: {pair['question']}\n\nA: {pair['answer']}"
        tokens = tokenize_for_retrieval(content)

        chunk = {
            "chunk_id": chunk_id,
            "agent_id": ext["agent_id"],
            "workspace_id": ext["workspace_id"],
            "content": content,
            "summary": pair["answer"][:200].strip(),
            "topic": pair.get("topic", "general"),
            "category": "qa_pair",
            "quality_score": pair.get("quality_score", 0.5),
            "tokens": tokens[:50],
            "source": {
                "type": "dojo_session",
                "session_id": ext["session_id"],
                "extraction_id": extraction_id,
                "roles": pair.get("roles", []),
            },
            "flagged": False,
            "created_at": now_iso(),
        }
        await db.agent_knowledge.insert_one(chunk)
        chunk_ids.append(chunk_id)

    await db.dojo_extracted_data.update_one(
        {"extraction_id": extraction_id},
        {"$set": {"status": "ingested", "ingested_chunk_ids": chunk_ids, "ingested_at": now_iso()}},
    )

    # Trigger dense embedding computation
    try:
        from gemini_embeddings import compute_and_store_dense_embeddings
        await compute_and_store_dense_embeddings(
            db, ext["agent_id"], ext["workspace_id"], chunk_ids
        )
    except Exception as e:
        logger.warning(f"Embedding computation deferred: {e}")

    return chunk_ids


def _clean_markers(text):
    """Strip Dojo structural markers from content."""
    text = re.sub(r'\[ROLE:\s*[^\]]+\]', '', text)
    text = re.sub(r'\[STATUS:\s*[^\]]+\]', '', text)
    text = re.sub(r'\[CONFIDENCE:\s*\d+%?\]', '', text)
    return text.strip()


def _score_pair_quality(question, answer, answer_turn):
    """Score a Q&A pair for training data quality (0.0-1.0).
    Weighted signals aligned with spec Section 5.2.
    """
    score = 0.0

    # Content Depth (weight: 0.25)
    ans_len = len(answer)
    if 100 <= ans_len <= 2000:
        score += 0.25
    elif ans_len > 2000:
        score += 0.20
    elif ans_len > 50:
        score += 0.10

    # Code Presence (weight: 0.15)
    if '```' in answer:
        score += 0.15

    # Confidence Level (weight: 0.15)
    confidence = answer_turn.get("confidence", {})
    score += 0.15 * confidence.get("score", 0.5)

    # Specificity (weight: 0.15) — technical terms present
    technical = ["function", "class", "def ", "import", "return", "API",
                 "database", "server", "http", "algorithm", "security"]
    specificity = sum(1 for m in technical if m.lower() in answer.lower())
    score += min(0.15, specificity * 0.03)

    # Cross-validation proxy (weight: 0.15)
    if len(question) > 50:
        score += 0.10  # Engaged exchange implies implicit validation

    return round(min(1.0, score), 3)
