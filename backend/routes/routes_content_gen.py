"""Content Generation Suite — AI docs, slides, sheets with export and templates"""
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)


class ContentCreateRequest(BaseModel):
    workspace_id: str
    content_type: str = "document"  # document, slides, spreadsheet
    title: str = Field(..., min_length=1)
    prompt: str = ""
    template_id: Optional[str] = None
    source_chat_id: Optional[str] = None
    source_artifact_ids: List[str] = []
    brand_config: dict = {}  # colors, fonts, tone
    model: str = "claude"


CONTENT_TEMPLATES = [
    {"template_id": "ct_project_brief", "content_type": "document", "name": "Project Brief", "category": "business", "structure": {"sections": ["Executive Summary", "Objectives", "Scope", "Timeline", "Budget", "Team"]}, "is_system": True},
    {"template_id": "ct_tech_spec", "content_type": "document", "name": "Technical Specification", "category": "technical", "structure": {"sections": ["Overview", "Architecture", "API Design", "Data Models", "Security", "Testing"]}, "is_system": True},
    {"template_id": "ct_pitch_deck", "content_type": "slides", "name": "Pitch Deck", "category": "business", "structure": {"slides": ["Title", "Problem", "Solution", "Market Size", "Business Model", "Traction", "Team", "Ask"]}, "is_system": True},
    {"template_id": "ct_quarterly_review", "content_type": "slides", "name": "Quarterly Review", "category": "business", "structure": {"slides": ["Title", "KPI Dashboard", "Achievements", "Challenges", "Next Quarter Goals", "Q&A"]}, "is_system": True},
    {"template_id": "ct_budget_tracker", "content_type": "spreadsheet", "name": "Budget Tracker", "category": "finance", "structure": {"sheets": [{"name": "Budget", "columns": ["Category", "Planned", "Actual", "Variance"]}]}, "is_system": True},
    {"template_id": "ct_project_plan", "content_type": "spreadsheet", "name": "Project Plan", "category": "project", "structure": {"sheets": [{"name": "Tasks", "columns": ["Task", "Owner", "Start", "End", "Status", "Priority"]}]}, "is_system": True},
]



def register_content_gen_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.post("/content/documents/create")
    async def create_document(data: ContentCreateRequest, request: Request):
        user = await get_current_user(request)
        content_id = f"doc_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # Build structure from template or prompt
        structure = {"sections": []}
        if data.template_id:
            tpl = next((t for t in CONTENT_TEMPLATES if t["template_id"] == data.template_id), None)
            if tpl:
                structure = tpl["structure"]

        # If source chat, gather messages
        source_content = ""
        if data.source_chat_id:
            msgs = await db.messages.find({"channel_id": data.source_chat_id, "sender_type": {"$in": ["human", "ai"]}}, {"_id": 0, "sender_name": 1, "content": 1}).sort("created_at", 1).to_list(100)
            source_content = "\n".join([f"[{m['sender_name']}]: {m['content']}" for m in msgs])

        if data.source_artifact_ids:
            for aid in data.source_artifact_ids[:5]:
                art = await db.artifacts.find_one({"artifact_id": aid}, {"_id": 0, "content": 1, "name": 1})
                if art:
                    source_content += f"\n\n--- {art.get('name', 'Artifact')} ---\n{art.get('content', '')}"

        doc = {
            "content_id": content_id, "workspace_id": data.workspace_id,
            "content_type": data.content_type, "title": data.title,
            "prompt": data.prompt, "source_content": source_content[:10000],
            "structure": structure, "version": 1,
            "model_used": data.model, "brand_config": data.brand_config,
            "status": "draft",
            "created_by": user["user_id"], "created_at": now, "updated_at": now,
        }
        await db.generated_content.insert_one(doc)
        await db.content_versions.insert_one({"content_id": content_id, "version": 1, "structure": structure, "created_at": now})
        return {k: v for k, v in doc.items() if k != "_id"}

    @api_router.post("/content/documents/{content_id}/edit")
    async def edit_document(content_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        doc = await db.generated_content.find_one({"content_id": content_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Content not found")
        new_ver = doc.get("version", 1) + 1
        structure = body.get("structure", doc.get("structure") or {})
        title = body.get("title", doc.get("title", ""))
        await db.generated_content.update_one({"content_id": content_id}, {"$set": {"structure": structure, "title": title, "version": new_ver, "updated_at": now_iso()}})
        await db.content_versions.insert_one({"content_id": content_id, "version": new_ver, "structure": structure, "diff_summary": body.get("diff_summary", "Edited"), "created_at": now_iso()})
        return await db.generated_content.find_one({"content_id": content_id}, {"_id": 0})

    @api_router.get("/content/documents/{content_id}")
    async def get_document(content_id: str, request: Request):
        await get_current_user(request)
        doc = await db.generated_content.find_one({"content_id": content_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        return doc

    @api_router.get("/content/documents")
    async def list_documents(request: Request, workspace_id: str = "", content_type: str = ""):
        await _authed_user(request, workspace_id)
        query = {}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if content_type:
            query["content_type"] = content_type
        docs = await db.generated_content.find(query, {"_id": 0, "source_content": 0}).sort("updated_at", -1).to_list(50)
        return {"documents": docs, "total": len(docs)}

    @api_router.delete("/content/documents/{content_id}")
    async def delete_document(content_id: str, request: Request):
        await get_current_user(request)
        await db.generated_content.delete_one({"content_id": content_id})
        await db.content_versions.delete_many({"content_id": content_id})
        return {"message": "Deleted"}

    @api_router.post("/content/documents/{content_id}/export")
    async def export_document(content_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        format_type = body.get("format", "md")  # md, json
        doc = await db.generated_content.find_one({"content_id": content_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        if format_type == "md":
            md = f"# {doc['title']}\n\n"
            for section in (doc.get("structure") or {}).get("sections") or []:
                if isinstance(section, str):
                    md += f"## {section}\n\n[Content to be generated]\n\n"
                elif isinstance(section, dict):
                    md += f"## {section.get('title', '')}\n\n{section.get('content', '')}\n\n"
            return {"content": md, "format": "markdown", "filename": f"{doc['title']}.md"}
        return {"content": json.dumps(doc.get("structure") or {}, indent=2), "format": "json", "filename": f"{doc['title']}.json"}

    # Slides
    @api_router.post("/content/slides/create")
    async def create_slides(data: ContentCreateRequest, request: Request):
        user = await get_current_user(request)
        data.content_type = "slides"
        content_id = f"slides_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        structure = {"slides": []}
        if data.template_id:
            tpl = next((t for t in CONTENT_TEMPLATES if t["template_id"] == data.template_id), None)
            if tpl:
                structure = tpl["structure"]
        doc = {"content_id": content_id, "workspace_id": data.workspace_id, "content_type": "slides", "title": data.title, "prompt": data.prompt, "structure": structure, "version": 1, "model_used": data.model, "brand_config": data.brand_config, "status": "draft", "created_by": user["user_id"], "created_at": now, "updated_at": now}
        await db.generated_content.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    # Sheets
    @api_router.post("/content/sheets/create")
    async def create_sheet(data: ContentCreateRequest, request: Request):
        user = await get_current_user(request)
        content_id = f"sheet_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        structure = {"sheets": [{"name": "Sheet1", "columns": [], "rows": []}]}
        if data.template_id:
            tpl = next((t for t in CONTENT_TEMPLATES if t["template_id"] == data.template_id), None)
            if tpl:
                structure = tpl["structure"]
        doc = {"content_id": content_id, "workspace_id": data.workspace_id, "content_type": "spreadsheet", "title": data.title, "prompt": data.prompt, "structure": structure, "version": 1, "model_used": data.model, "status": "draft", "created_by": user["user_id"], "created_at": now, "updated_at": now}
        await db.generated_content.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    # Chat to document
    @api_router.post("/content/from-chat")
    async def chat_to_document(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        channel_id = body.get("channel_id", "")
        output_type = body.get("output_type", "document")  # document, slides, report
        title = body.get("title", "Chat Export")
        msgs = await db.messages.find({"channel_id": channel_id, "sender_type": {"$in": ["human", "ai"]}}, {"_id": 0}).sort("created_at", 1).to_list(200)
        content_id = f"doc_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        structure = {"sections": [{"title": "Conversation", "content": "\n".join([f"**{m.get('sender_name','')}**: {m.get('content','')}" for m in msgs])}]}
        doc = {"content_id": content_id, "workspace_id": body.get("workspace_id", ""), "content_type": output_type, "title": title, "structure": structure, "version": 1, "status": "draft", "created_by": user["user_id"], "created_at": now, "updated_at": now}
        await db.generated_content.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    # Templates
    @api_router.get("/content/templates")
    async def list_content_templates(request: Request, content_type: str = ""):
        await get_current_user(request)
        templates = [t for t in CONTENT_TEMPLATES if not content_type or t["content_type"] == content_type]
        custom = await db.content_templates.find({"content_type": content_type} if content_type else {}, {"_id": 0}).to_list(20)
        return {"templates": templates + custom}
