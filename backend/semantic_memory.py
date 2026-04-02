"""Semantic Memory — Embedding-based retrieval for agent context.

Instead of loading the last N messages by recency, embed the user's query
and retrieve the most semantically relevant messages from full history.
Uses a lightweight local embedding approach (TF-IDF + cosine similarity)
that works without an external vector DB.
"""
import logging
import re
from collections import Counter
from math import sqrt
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


STOP_WORDS = frozenset([
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "this", "that",
    "these", "those", "i", "you", "he", "she", "it", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "its", "our", "their",
    "what", "which", "who", "whom", "not", "no", "so", "if", "then",
    "than", "too", "very", "just", "about", "up", "out", "all", "also",
])

def _tokenize(text: str) -> List[str]:
    """Tokenizer with stop word removal and camelCase splitting."""
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ')
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def _compute_tfidf(documents: List[str]) -> List[Dict[str, float]]:
    """Compute TF-IDF vectors for a list of documents."""
    doc_freq = Counter()
    doc_tokens = []
    
    for doc in documents:
        tokens = set(_tokenize(doc))
        doc_tokens.append(_tokenize(doc))
        for t in tokens:
            doc_freq[t] += 1
    
    n_docs = len(documents)
    vectors = []
    vocab = list(doc_freq.keys())
    vocab_idx = {w: i for i, w in enumerate(vocab)}
    
    for tokens in doc_tokens:
        tf = Counter(tokens)
        vec = {}
        for token, count in tf.items():
            if token in vocab_idx:
                idf = 1.0 + (n_docs / (1 + doc_freq[token]))
                vec[vocab_idx[token]] = (count / max(len(tokens), 1)) * idf
        vectors.append(vec)
    
    return vectors, vocab_idx


def _cosine_sim(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    keys = set(v1.keys()) & set(v2.keys())
    if not keys:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in keys)
    mag1 = sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


async def retrieve_relevant_messages(db, channel_id: str, query: str, max_results: int = 10, max_history: int = 200) -> List[Dict[str, Any]]:
    """Retrieve the most semantically relevant messages for a query.
    
    Fetches up to max_history messages, computes TF-IDF similarity with the query,
    and returns the top max_results most relevant messages.
    """
    # Fetch message history
    messages = await db.messages.find(
        {"channel_id": channel_id},
        {"_id": 0, "message_id": 1, "sender_name": 1, "content": 1, "created_at": 1, "sender_type": 1}
    ).sort("created_at", -1).limit(max_history).to_list(max_history)
    
    if not messages or not query.strip():
        return messages[:max_results]
    
    # Build document list: query + all messages
    docs = [query] + [m.get("content", "") for m in messages]
    
    try:
        vectors, _ = _compute_tfidf(docs)
        query_vec = vectors[0]
        
        # Score each message
        scored = []
        for i, msg in enumerate(messages):
            sim = _cosine_sim(query_vec, vectors[i + 1])
            scored.append((sim, msg))
        
        # Sort by relevance
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return top results
        return [msg for _, msg in scored[:max_results]]
    except Exception as e:
        logger.debug(f"Semantic retrieval failed, falling back to recency: {e}")
        return messages[:max_results]


async def build_semantic_context(db, channel_id: str, latest_message: str, max_recent: int = 15, max_relevant: int = 10) -> str:
    """Build a hybrid context: recent messages + semantically relevant older messages.
    
    Returns a combined context string with both recency and relevance.
    """
    # Get recent messages (always include these)
    recent = await db.messages.find(
        {"channel_id": channel_id},
        {"_id": 0, "message_id": 1, "sender_name": 1, "content": 1, "created_at": 1}
    ).sort("created_at", -1).limit(max_recent).to_list(max_recent)
    recent.reverse()
    
    recent_ids = {m["message_id"] for m in recent}
    
    # Get semantically relevant messages (may overlap with recent)
    relevant = await retrieve_relevant_messages(db, channel_id, latest_message, max_results=max_relevant, max_history=200)
    
    # Combine: recent first, then relevant that aren't already included
    combined = list(recent)
    for msg in relevant:
        if msg.get("message_id") not in recent_ids:
            combined.append(msg)
            recent_ids.add(msg.get("message_id"))
    
    # Build context string
    context = "Here is the conversation context (recent messages + relevant history):\n\n"
    max_chars = 15000
    
    for msg in combined:
        sender = msg.get("sender_name", "Unknown")
        content = msg.get("content", "")
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        entry = f"[{sender}]: {content}\n\n"
        if len(context) + len(entry) > max_chars:
            context += "[... context limit reached]\n\n"
            break
        context += entry
    
    return context, len(combined)
