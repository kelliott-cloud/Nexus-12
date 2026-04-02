"""Research Document Ingestion — Deep parsing, structure detection, paragraph indexing."""
import re
import logging
from nexus_utils import now_iso, gen_id
from semantic_memory import _tokenize

logger = logging.getLogger(__name__)


async def ingest_document(db, file_bytes: bytes, filename: str, library_id: str, workspace_id: str, user_id: str):
    doc_id = gen_id("rdoc")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    doc = {
        "doc_id": doc_id, "workspace_id": workspace_id, "library_id": library_id,
        "title": filename, "authors": [], "abstract": "", "doi": None, "pmid": None, "arxiv_id": None,
        "publication_date": None, "journal": None, "page_count": 0, "word_count": 0, "language": "en",
        "sections": [], "references": [], "figures": [], "ingestion_status": "processing",
        "chunk_count": 0, "tags": [], "imported_from": "upload", "uploaded_by": user_id,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.research_documents.insert_one(doc)
    try:
        text, pages, figures = await _extract_text(file_bytes, ext)
        if len(text.strip()) < 100:
            await db.research_documents.update_one({"doc_id": doc_id}, {"$set": {
                "ingestion_status": "extraction_failed",
                "error": f"Insufficient text extracted ({len(text.strip())} chars). The document may be scanned/image-based and requires OCR.",
                "updated_at": now_iso()}})
            return doc_id
        metadata = await _parse_structure(db, text, workspace_id)
        chunks = _paragraph_chunk(text, metadata.get("sections", []))
        for i, chunk in enumerate(chunks):
            await db.research_chunks.insert_one({
                "chunk_id": gen_id("rchk"), "doc_id": doc_id, "workspace_id": workspace_id,
                "section_title": chunk["section"], "page_num": chunk.get("page", 0), "para_index": i,
                "content": chunk["text"], "content_type": "text",
                "inline_citations": _extract_citation_numbers(chunk["text"]),
                "bm25_tokens": list(set(_tokenize(chunk["text"]))), "token_count": len(chunk["text"].split()),
                "created_at": now_iso(),
            })
        await db.research_documents.update_one({"doc_id": doc_id}, {"$set": {
            "title": metadata.get("title", filename), "authors": metadata.get("authors", []),
            "abstract": metadata.get("abstract", ""), "doi": metadata.get("doi"),
            "sections": metadata.get("sections", []), "references": metadata.get("references", []),
            "figures": [{"figure_id": gen_id("fig"), **f} for f in figures],
            "page_count": pages, "word_count": len(text.split()), "chunk_count": len(chunks),
            "ingestion_status": "completed", "updated_at": now_iso(),
        }})
        try:
            from knowledge_graph import KnowledgeGraphEngine, ConsentChecker
            if await ConsentChecker.is_workspace_kg_enabled(db, workspace_id):
                import asyncio
                kg = KnowledgeGraphEngine(db)
                fake_msg = {"content": f"Research paper: {metadata.get('title','')}. {metadata.get('abstract','')[:1000]}",
                            "channel_id": "", "message_id": doc_id, "sender_id": user_id, "sender_type": "human"}
                asyncio.create_task(kg.extract_entities_from_message(fake_msg, {}, workspace_id))
        except Exception:
            pass
        return doc_id
    except Exception as e:
        logger.error(f"Ingestion failed for {doc_id}: {e}")
        await db.research_documents.update_one({"doc_id": doc_id}, {"$set": {"ingestion_status": "failed", "error": str(e)[:500]}})
        raise


async def _extract_text(file_bytes, ext):
    figures = []
    if ext == "pdf":
        import PyPDF2, io
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = len(reader.pages)
        text = "\n\n".join([page.extract_text() or "" for page in reader.pages])
        return text, pages, figures
    elif ext in ("docx", "doc"):
        import docx as python_docx, io
        doc = python_docx.Document(io.BytesIO(file_bytes))
        text = "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        return text, 0, figures
    else:
        return file_bytes.decode("utf-8", errors="ignore"), 0, figures


async def _parse_structure(db, text, workspace_id):
    from collaboration_core import get_ai_key_for_agent
    from ai_providers import call_ai_direct
    for agent in ["groq", "deepseek", "gemini", "chatgpt"]:
        api_key, _ = await get_ai_key_for_agent("system", workspace_id, agent)
        if api_key:
            try:
                from workflow_engine import parse_ai_json
                result = await call_ai_direct(agent, api_key,
                    "Extract structured metadata from this document. Return ONLY JSON.",
                    f'Extract from this document:\n{text[:6000]}\n\nReturn JSON: {{"title":"...", "authors":["..."], "abstract":"...", "doi":"..." or null, "sections":[{{"title":"..."}}], "references":[{{"ref_num":1, "text":"..."}}]}}',
                    workspace_id=workspace_id, db=db)
                return parse_ai_json(result)
            except Exception:
                continue
    return {"title": "", "authors": [], "abstract": text[:500]}


def _paragraph_chunk(text, sections):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 20]
    current_section = "Document"
    section_titles = [s.get("title", "") for s in sections]
    chunks = []
    for para in paragraphs:
        for st in section_titles:
            if st and st.lower() in para.lower()[:len(st) + 20]:
                current_section = st
                break
        chunks.append({"text": para, "section": current_section})
    return chunks


def _extract_citation_numbers(text):
    refs = set()
    for m in re.finditer(r"\[(\d+(?:[,\s-]\d+)*)\]", text):
        for part in m.group(1).split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-")
                    refs.update(range(int(start), int(end) + 1))
                except Exception:
                    pass
            else:
                try:
                    refs.add(int(part))
                except Exception:
                    pass
    return sorted(refs)
