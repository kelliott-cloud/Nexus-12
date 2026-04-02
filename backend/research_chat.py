"""Citation-Linked Research Chat — AI responses with paragraph-level source attribution."""
import logging
from semantic_memory import _tokenize

logger = logging.getLogger(__name__)


async def research_chat(db, query: str, library_id: str, workspace_id: str, model: str = "claude", max_chunks: int = 15):
    chunks = await _retrieve_relevant_chunks(db, query, library_id, workspace_id, max_chunks)
    if not chunks:
        return {"answer": "No relevant content found in your research library.", "citations": {}}
    citation_context = ""
    citation_map = {}
    for i, chunk in enumerate(chunks):
        doc = await db.research_documents.find_one({"doc_id": chunk["doc_id"]}, {"_id": 0, "title": 1})
        marker = f"[SRC{i + 1}]"
        citation_context += f'\n{marker} (From: "{doc.get("title", "?")}", Section: {chunk["section_title"]}, Page {chunk["page_num"]}, Para {chunk["para_index"]}):\n{chunk["content"]}\n'
        citation_map[marker] = {
            "chunk_id": chunk["chunk_id"], "doc_id": chunk["doc_id"],
            "doc_title": doc.get("title", ""), "section": chunk["section_title"],
            "page": chunk["page_num"], "para_index": chunk["para_index"],
            "excerpt": chunk["content"][:200],
        }
    system_prompt = """You are a research assistant analyzing documents in a research library.
Answer the question using ONLY the provided source material.
CRITICAL: Cite your sources inline using the [SRC#] markers provided.
Every factual claim MUST have a citation.
Example: "Transformers use self-attention [SRC1] which improves parallelization [SRC3]."
If the sources do not contain enough information, say so explicitly."""
    user_prompt = f"SOURCES:\n{citation_context}\n\nQUESTION: {query}"
    from collaboration_core import get_ai_key_for_agent
    from ai_providers import call_ai_direct
    api_key, _ = await get_ai_key_for_agent("system", workspace_id, model)
    if not api_key:
        return {"answer": f"No API key for {model}", "citations": {}}
    answer = await call_ai_direct(model, api_key, system_prompt, user_prompt, workspace_id=workspace_id, db=db)
    return {"answer": answer, "citations": citation_map, "chunks_used": len(chunks)}


async def _retrieve_relevant_chunks(db, query, library_id, workspace_id, max_chunks=15):
    doc_ids = [d["doc_id"] async for d in db.research_documents.find(
        {"library_id": library_id, "workspace_id": workspace_id, "ingestion_status": "completed"},
        {"_id": 0, "doc_id": 1})]
    if not doc_ids:
        return []
    chunks = await db.research_chunks.find(
        {"doc_id": {"$in": doc_ids}, "workspace_id": workspace_id}, {"_id": 0}
    ).limit(500).to_list(500)
    query_tokens = set(_tokenize(query.lower()))
    scored = []
    for c in chunks:
        overlap = len(query_tokens & set(c.get("bm25_tokens", [])))
        if overlap > 0:
            scored.append((c, overlap))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max_chunks]]
