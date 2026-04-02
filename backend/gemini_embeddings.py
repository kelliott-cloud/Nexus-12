"""Gemini Dense Vector Embeddings — generates 768-dim vectors via Google Gemini API.

Used for semantic search in the RAG pipeline. Falls back gracefully if API is unavailable.
"""
import os
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
BATCH_SIZE = 50


def _get_client():
    """Get Gemini client. Returns None if key is missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai
    return genai.Client(api_key=api_key)


def _embed_batch_sync(client, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
    """Synchronous embedding call for use in thread pool."""
    from google.genai import types
    config = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIM,
    )
    result = client.models.embed_content(
        model=GEMINI_MODEL,
        contents=texts,
        config=config,
    )
    return [list(e.values) for e in result.embeddings]


async def generate_embeddings(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[List[List[float]]]:
    """Generate dense vector embeddings for a list of texts.
    
    Returns list of 768-dim float vectors, or None on failure.
    Processes in batches to respect API rate limits.
    """
    client = _get_client()
    if not client:
        logger.warning("GEMINI_API_KEY not set — skipping dense embeddings")
        return None

    if not texts:
        return []

    loop = asyncio.get_event_loop()
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        try:
            batch_embeddings = await loop.run_in_executor(
                None, _embed_batch_sync, client, batch, task_type
            )
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"Gemini embedding batch {i // BATCH_SIZE} failed: {e}")
            return None
        if i + BATCH_SIZE < len(texts):
            await asyncio.sleep(0.3)

    return all_embeddings


async def generate_query_embedding(query: str) -> Optional[List[float]]:
    """Generate a single query embedding optimized for retrieval."""
    result = await generate_embeddings([query], task_type="RETRIEVAL_QUERY")
    if result and len(result) > 0:
        return result[0]
    return None


def cosine_similarity_dense(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two dense vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sum(a * a for a in vec_a) ** 0.5
    mag_b = sum(b * b for b in vec_b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


async def compute_and_store_dense_embeddings(db, agent_id: str, workspace_id: str) -> int:
    """Compute Gemini dense embeddings for all knowledge chunks and store in MongoDB."""
    chunks = await db.agent_knowledge.find(
        {"agent_id": agent_id, "workspace_id": workspace_id, "flagged": {"$ne": True}},
        {"_id": 1, "content": 1, "text": 1}
    ).to_list(500)

    if not chunks:
        return 0

    texts = [c.get("content") or c.get("text", "") for c in chunks]
    embeddings = await generate_embeddings(texts)
    if embeddings is None:
        logger.warning(f"Dense embedding generation failed for agent={agent_id}")
        return 0

    stored = 0
    for chunk, emb in zip(chunks, embeddings):
        await db.agent_knowledge.update_one(
            {"_id": chunk["_id"]},
            {"$set": {"dense_vector": emb}}
        )
        stored += 1

    # Store metadata
    await db.agent_embeddings_meta.update_one(
        {"agent_id": agent_id, "workspace_id": workspace_id},
        {"$set": {
            "dense_model": GEMINI_MODEL,
            "dense_dim": EMBEDDING_DIM,
            "dense_doc_count": stored,
        }},
        upsert=True
    )

    logger.info(f"Stored {stored} dense embeddings (agent={agent_id}, dim={EMBEDDING_DIM})")
    return stored


async def retrieve_with_dense_embeddings(
    db, agent_id: str, workspace_id: str, query: str, top_k: int = 5
) -> list:
    """Retrieve top-k chunks using dense vector cosine similarity."""
    query_vec = await generate_query_embedding(query)
    if not query_vec:
        return []

    chunks = await db.agent_knowledge.find(
        {
            "agent_id": agent_id,
            "workspace_id": workspace_id,
            "flagged": {"$ne": True},
            "dense_vector": {"$exists": True},
        },
        {"_id": 0, "chunk_id": 1, "content": 1, "text": 1, "topic": 1,
         "source": 1, "summary": 1, "quality_score": 1, "dense_vector": 1}
    ).to_list(500)

    scored = []
    for chunk in chunks:
        vec = chunk.get("dense_vector")
        if not vec:
            continue
        score = cosine_similarity_dense(query_vec, vec)
        if score > 0.1:
            chunk_copy = {k: v for k, v in chunk.items() if k != "dense_vector"}
            chunk_copy["relevance_score"] = round(score, 4)
            scored.append(chunk_copy)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored[:top_k]
