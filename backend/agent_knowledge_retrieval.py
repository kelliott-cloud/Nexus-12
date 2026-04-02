"""Runtime knowledge retrieval for agent prompt injection.

Retrieves the most relevant training knowledge chunks for a given query
and formats them for injection into the agent's system prompt.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger("agent_knowledge_retrieval")


async def retrieve_training_knowledge(
    db, agent_id: str, query: str,
    max_chunks: int = 8, max_tokens: int = 3000,
    min_relevance: float = 0.3, strategy: str = "semantic"
) -> str:
    """Retrieve relevant training knowledge for an agent given a user query.

    Returns formatted context string ready for prompt injection.
    """
    knowledge_chunks = await db.agent_knowledge.find(
        {"agent_id": agent_id, "flagged": {"$ne": True}},
        {"_id": 0, "chunk_id": 1, "content": 1, "summary": 1, "category": 1,
         "topic": 1, "source": 1, "quality_score": 1, "tokens": 1, "token_count": 1,
         "bm25_vector": 1, "dense_vector": 1}
    ).sort("quality_score", -1).limit(200).to_list(200)

    if not knowledge_chunks or not query.strip():
        return ""

    if strategy == "recency":
        selected = knowledge_chunks[:max_chunks]
    elif strategy == "semantic":
        selected = await _semantic_select(query, knowledge_chunks, max_chunks, min_relevance)
    else:
        # Hybrid: semantic top + recency top
        semantic_top = await _semantic_select(query, knowledge_chunks, 5, min_relevance)
        recency_top = knowledge_chunks[:3]
        seen = set()
        selected = []
        for c in semantic_top + recency_top:
            cid = c.get("chunk_id", "")
            if cid not in seen:
                seen.add(cid)
                selected.append(c)

    if not selected:
        return ""

    lines = []
    total_tokens = 0
    now = datetime.now(timezone.utc).isoformat()
    for chunk in selected:
        content = chunk.get("content", "")
        tokens = chunk.get("token_count") or len(content.split())
        if total_tokens + tokens > max_tokens:
            break
        category = chunk.get("category", "fact")
        source = chunk.get("source") or {}
        source_title = source.get("title", "Unknown") if isinstance(source, dict) else "Unknown"
        source_domain = source.get("domain", "") if isinstance(source, dict) else ""
        lines.append(f"[{category.upper()}] {content}")
        if source_domain:
            lines.append(f"  Source: {source_title} ({source_domain})")
        total_tokens += tokens
        await db.agent_knowledge.update_one(
            {"chunk_id": chunk["chunk_id"]},
            {"$inc": {"times_retrieved": 1}, "$set": {"last_retrieved": now}}
        )

    if not lines:
        return ""

    return (
        "\n\n=== TRAINING DATA (Domain Knowledge) ===\n"
        "The following is your specialized training knowledge. Use it to inform your responses. "
        "Cite sources when directly referencing this information.\n\n"
        + "\n\n".join(lines)
        + "\n=== END TRAINING DATA ===\n"
    )


async def _semantic_select(query, chunks, max_chunks, min_relevance):
    """Select chunks using dense Gemini embeddings (preferred), BM25, or TF-IDF fallback."""
    # Try dense Gemini embeddings first (highest quality)
    try:
        dense_chunks = [c for c in chunks if c.get("dense_vector")]
        if dense_chunks:
            from gemini_embeddings import generate_query_embedding, cosine_similarity_dense
            query_vec = await generate_query_embedding(query)
            if query_vec:
                scored = []
                for chunk in dense_chunks:
                    sim = cosine_similarity_dense(query_vec, chunk.get("dense_vector") or [])
                    if sim >= min_relevance:
                        scored.append((sim, chunk))
                scored.sort(key=lambda x: x[0], reverse=True)
                if scored:
                    logger.debug(f"Dense retrieval: {len(scored)} results for query")
                    return [chunk for _, chunk in scored[:max_chunks]]
    except Exception as e:
        logger.debug(f"Dense retrieval failed, falling back to BM25: {e}")

    # Try BM25 embeddings (sparse vector fallback)
    try:
        bm25_chunks = [c for c in chunks if c.get("bm25_vector")]
        if bm25_chunks:
            from ai_embeddings import compute_query_vector, cosine_similarity
            all_terms = set()
            for c in bm25_chunks:
                all_terms.update(c.get("bm25_vector", {}).keys())
            idf = {t: 1.0 for t in all_terms}
            query_vec = compute_query_vector(query, idf)
            if query_vec:
                scored = []
                for chunk in bm25_chunks:
                    sim = cosine_similarity(query_vec, chunk.get("bm25_vector", {}))
                    if sim >= min_relevance:
                        scored.append((sim, chunk))
                scored.sort(key=lambda x: x[0], reverse=True)
                if scored:
                    return [chunk for _, chunk in scored[:max_chunks]]
    except Exception as e:
        logger.debug(f"BM25 retrieval failed, falling back to TF-IDF: {e}")

    # Final fallback: TF-IDF
    from semantic_memory import _compute_tfidf, _cosine_sim
    try:
        docs = [query] + [c.get("content", "") for c in chunks]
        vectors, _ = _compute_tfidf(docs)
        query_vec = vectors[0]
        scored = []
        for i, chunk in enumerate(chunks):
            sim = _cosine_sim(query_vec, vectors[i + 1])
            if sim >= min_relevance:
                scored.append((sim, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:max_chunks]]
    except Exception as e:
        logger.debug(f"TF-IDF retrieval failed: {e}")
        return chunks[:max_chunks]
