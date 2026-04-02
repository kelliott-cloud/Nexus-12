"""Enhanced Embeddings — TF-IDF with n-grams and BM25 scoring for semantic retrieval.
Stores computed vectors in MongoDB for fast similarity search."""
import math
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# BM25 parameters
K1 = 1.5
B = 0.75
NGRAM_RANGE = (1, 2)  # unigrams + bigrams


def tokenize(text: str) -> list:
    """Tokenize text into cleaned lowercased words."""
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return [w for w in text.split() if len(w) > 1]


def ngrams(tokens: list, n: int) -> list:
    """Generate n-grams from token list."""
    return ["_".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def extract_features(text: str) -> list:
    """Extract unigram + bigram features from text."""
    tokens = tokenize(text)
    features = list(tokens)
    if len(tokens) >= 2:
        features.extend(ngrams(tokens, 2))
    return features


def compute_bm25_vectors(documents: list) -> tuple:
    """Compute BM25-weighted TF-IDF vectors for a corpus.
    Returns (vocabulary, idf_scores, doc_vectors) where doc_vectors is list of dicts."""
    if not documents:
        return [], {}, []

    doc_features = [extract_features(doc) for doc in documents]
    avg_dl = sum(len(f) for f in doc_features) / max(len(doc_features), 1)
    N = len(doc_features)

    # Build vocabulary and document frequency
    df = Counter()
    for features in doc_features:
        unique = set(features)
        for term in unique:
            df[term] += 1

    # IDF with BM25 variant
    idf = {}
    for term, freq in df.items():
        idf[term] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)

    # BM25 scores per document
    vectors = []
    for features in doc_features:
        tf = Counter(features)
        dl = len(features)
        vec = {}
        for term, count in tf.items():
            if term in idf:
                numerator = count * (K1 + 1)
                denominator = count + K1 * (1 - B + B * dl / max(avg_dl, 1))
                vec[term] = idf[term] * numerator / denominator
        vectors.append(vec)

    vocab = sorted(idf.keys())
    return vocab, idf, vectors


def compute_query_vector(query: str, idf: dict) -> dict:
    """Compute BM25 vector for a query against existing IDF scores."""
    features = extract_features(query)
    tf = Counter(features)
    vec = {}
    for term, count in tf.items():
        if term in idf:
            vec[term] = idf[term] * (count * (K1 + 1)) / (count + K1)
    return vec


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """Compute cosine similarity between two sparse vectors (dicts)."""
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


async def compute_and_store_embeddings(db, agent_id: str, workspace_id: str):
    """Compute BM25 vectors for all chunks and store them in MongoDB."""
    chunks = await db.agent_knowledge.find(
        {"agent_id": agent_id, "workspace_id": workspace_id, "flagged": {"$ne": True}},
        {"_id": 1, "text": 1}
    ).to_list(500)

    if not chunks:
        return 0

    texts = [c.get("text", "") for c in chunks]
    vocab, idf, vectors = compute_bm25_vectors(texts)

    # Store IDF corpus-level data
    await db.agent_embeddings_meta.update_one(
        {"agent_id": agent_id, "workspace_id": workspace_id},
        {"$set": {"idf": idf, "vocab_size": len(vocab), "doc_count": len(chunks)}},
        upsert=True
    )

    # Store per-chunk vectors
    for chunk, vec in zip(chunks, vectors):
        # Convert dict vector to storable format (only non-zero terms)
        sparse_vec = {k: round(v, 4) for k, v in vec.items() if v > 0.01}
        await db.agent_knowledge.update_one(
            {"_id": chunk["_id"]},
            {"$set": {"bm25_vector": sparse_vec}}
        )

    logger.info(f"Computed BM25 embeddings for {len(chunks)} chunks (agent={agent_id})")
    return len(chunks)


async def retrieve_with_embeddings(db, agent_id: str, workspace_id: str, query: str, top_k: int = 5) -> list:
    """Retrieve top-k chunks using BM25 similarity."""
    # Load IDF data
    meta = await db.agent_embeddings_meta.find_one(
        {"agent_id": agent_id, "workspace_id": workspace_id},
        {"_id": 0, "idf": 1}
    )
    if not meta or not meta.get("idf"):
        return []

    idf = meta["idf"]
    query_vec = compute_query_vector(query, idf)
    if not query_vec:
        return []

    # Load chunks with vectors
    chunks = await db.agent_knowledge.find(
        {"agent_id": agent_id, "workspace_id": workspace_id, "flagged": {"$ne": True}, "bm25_vector": {"$exists": True}},
        {"_id": 0, "chunk_id": 1, "text": 1, "topic": 1, "source": 1, "summary": 1, "quality_score": 1, "bm25_vector": 1}
    ).to_list(500)

    # Score each chunk
    scored = []
    for chunk in chunks:
        vec = chunk.get("bm25_vector", {})
        score = cosine_similarity(query_vec, vec)
        if score > 0:
            chunk_copy = {k: v for k, v in chunk.items() if k != "bm25_vector"}
            chunk_copy["relevance_score"] = round(score, 4)
            scored.append(chunk_copy)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored[:top_k]
