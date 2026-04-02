"""Wiki/Docs Module - Per-workspace wiki with page hierarchy, versioning, and AI access"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso, safe_regex

logger = logging.getLogger(__name__)



class WikiPageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = ""
    parent_id: Optional[str] = None
    icon: str = ""


class WikiPageUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    parent_id: Optional[str] = None
    icon: Optional[str] = None
    pinned: Optional[bool] = None


def register_wiki_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.get("/workspaces/{workspace_id}/wiki")
    async def list_wiki_pages(workspace_id: str, request: Request, search: Optional[str] = None):
        """List all wiki pages for a workspace (tree-friendly)"""
        user = await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        if search:
            query["$or"] = [
                {"title": {"$regex": safe_regex(search), "$options": "i"}},
                {"content": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        pages = await db.wiki_pages.find(
            query,
            {"_id": 0, "page_id": 1, "title": 1, "parent_id": 1, "icon": 1,
             "pinned": 1, "updated_at": 1, "updated_by_name": 1, "word_count": 1}
        ).sort("title", 1).to_list(500)
        return {"pages": pages}

    @api_router.post("/workspaces/{workspace_id}/wiki")
    async def create_wiki_page(workspace_id: str, data: WikiPageCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        now = now_iso()
        page_id = f"wp_{uuid.uuid4().hex[:12]}"
        word_count = len(data.content.split()) if data.content else 0
        page = {
            "page_id": page_id,
            "workspace_id": workspace_id,
            "title": data.title.strip(),
            "content": data.content,
            "parent_id": data.parent_id,
            "icon": data.icon or "",
            "pinned": False,
            "word_count": word_count,
            "version": 1,
            "created_by": user["user_id"],
            "created_by_name": user.get("name", "Unknown"),
            "updated_by": user["user_id"],
            "updated_by_name": user.get("name", "Unknown"),
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        }
        await db.wiki_pages.insert_one(page)
        # KG ambient learning hook
        try:
            from knowledge_graph_hooks import on_wiki_page_saved
            import asyncio
            asyncio.create_task(on_wiki_page_saved(db, {"page_id": page_id, "title": data.title.strip(), "content": data.content[:2000], "updated_by": user["user_id"]}, workspace_id))
        except Exception:
            pass
        # Save version
        await db.wiki_versions.insert_one({
            "version_id": f"wv_{uuid.uuid4().hex[:12]}",
            "page_id": page_id,
            "version": 1,
            "title": data.title.strip(),
            "content": data.content,
            "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "created_at": now,
        })
        return {k: v for k, v in page.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/wiki/{page_id}")
    async def get_wiki_page(workspace_id: str, page_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        page = await db.wiki_pages.find_one(
            {"page_id": page_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}},
            {"_id": 0}
        )
        if not page:
            raise HTTPException(404, "Page not found")
        # Get child pages
        children = await db.wiki_pages.find(
            {"workspace_id": workspace_id, "parent_id": page_id, "is_deleted": {"$ne": True}},
            {"_id": 0, "page_id": 1, "title": 1, "icon": 1}
        ).sort("title", 1).to_list(100)
        page["children"] = children
        return page

    @api_router.put("/workspaces/{workspace_id}/wiki/{page_id}")
    async def update_wiki_page(workspace_id: str, page_id: str, data: WikiPageUpdate, request: Request):
        user = await _authed_user(request, workspace_id)
        page = await db.wiki_pages.find_one(
            {"page_id": page_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        )
        if not page:
            raise HTTPException(404, "Page not found")
        now = now_iso()
        updates = {"updated_at": now, "updated_by": user["user_id"], "updated_by_name": user.get("name", "Unknown")}
        content_changed = False
        if data.title is not None:
            updates["title"] = data.title.strip()
        if data.content is not None:
            updates["content"] = data.content
            updates["word_count"] = len(data.content.split()) if data.content else 0
            content_changed = True
        if data.parent_id is not None:
            updates["parent_id"] = data.parent_id if data.parent_id else None
        if data.icon is not None:
            updates["icon"] = data.icon
        if data.pinned is not None:
            updates["pinned"] = data.pinned
        if content_changed:
            new_version = page.get("version", 0) + 1
            updates["version"] = new_version
            await db.wiki_versions.insert_one({
                "version_id": f"wv_{uuid.uuid4().hex[:12]}",
                "page_id": page_id,
                "version": new_version,
                "title": updates.get("title", page["title"]),
                "content": data.content,
                "author_id": user["user_id"],
                "author_name": user.get("name", "Unknown"),
                "created_at": now,
            })
        await db.wiki_pages.update_one({"page_id": page_id}, {"$set": updates})
        result = await db.wiki_pages.find_one({"page_id": page_id}, {"_id": 0})
        return result

    @api_router.delete("/workspaces/{workspace_id}/wiki/{page_id}")
    async def delete_wiki_page(workspace_id: str, page_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        # Soft delete + unparent children
        await db.wiki_pages.update_one(
            {"page_id": page_id, "workspace_id": workspace_id},
            {"$set": {"is_deleted": True, "updated_at": now_iso()}}
        )
        await db.wiki_pages.update_many(
            {"parent_id": page_id, "workspace_id": workspace_id},
            {"$set": {"parent_id": None}}
        )
        return {"deleted": True}

    @api_router.get("/workspaces/{workspace_id}/wiki/{page_id}/history")
    async def get_wiki_history(workspace_id: str, page_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        versions = await db.wiki_versions.find(
            {"page_id": page_id},
            {"_id": 0}
        ).sort("version", -1).limit(50).to_list(50)
        return {"versions": versions}

    @api_router.get("/workspaces/{workspace_id}/wiki/{page_id}/version/{version}")
    async def get_wiki_version(workspace_id: str, page_id: str, version: int, request: Request):
        user = await _authed_user(request, workspace_id)
        v = await db.wiki_versions.find_one(
            {"page_id": page_id, "version": version},
            {"_id": 0}
        )
        if not v:
            raise HTTPException(404, "Version not found")
        return v

    # AI agent wiki access
    @api_router.post("/workspaces/{workspace_id}/wiki/ai-update")
    async def ai_update_wiki(workspace_id: str, request: Request):
        """AI agents can create/update wiki pages"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        title = body.get("title", "").strip()
        content = body.get("content", "")
        agent_name = body.get("agent_name", "AI Agent")
        if not title:
            raise HTTPException(400, "title required")
        now = now_iso()
        # Check if page exists by title
        existing = await db.wiki_pages.find_one(
            {"workspace_id": workspace_id, "title": title, "is_deleted": {"$ne": True}}
        )
        if existing:
            new_ver = existing.get("version", 0) + 1
            await db.wiki_pages.update_one(
                {"page_id": existing["page_id"]},
                {"$set": {"content": content, "version": new_ver,
                          "word_count": len(content.split()),
                          "updated_by": f"ai:{agent_name}", "updated_by_name": agent_name,
                          "updated_at": now}}
            )
            await db.wiki_versions.insert_one({
                "version_id": f"wv_{uuid.uuid4().hex[:12]}",
                "page_id": existing["page_id"], "version": new_ver,
                "title": title, "content": content,
                "author_id": f"ai:{agent_name}", "author_name": agent_name,
                "created_at": now,
            })
            return {"page_id": existing["page_id"], "action": "updated", "version": new_ver}
        else:
            page_id = f"wp_{uuid.uuid4().hex[:12]}"
            await db.wiki_pages.insert_one({
                "page_id": page_id, "workspace_id": workspace_id,
                "title": title, "content": content, "parent_id": None,
                "icon": "", "pinned": False,
                "word_count": len(content.split()),
                "version": 1,
                "created_by": f"ai:{agent_name}", "created_by_name": agent_name,
                "updated_by": f"ai:{agent_name}", "updated_by_name": agent_name,
                "created_at": now, "updated_at": now, "is_deleted": False,
            })
            await db.wiki_versions.insert_one({
                "version_id": f"wv_{uuid.uuid4().hex[:12]}",
                "page_id": page_id, "version": 1,
                "title": title, "content": content,
                "author_id": f"ai:{agent_name}", "author_name": agent_name,
                "created_at": now,
            })
            return {"page_id": page_id, "action": "created", "version": 1}


    # ============ Wiki Page Templates ============

    WIKI_TEMPLATES = [
        {
            "template_id": "tpl_meeting_notes",
            "name": "Meeting Notes",
            "icon": "",
            "content": "# Meeting Notes\n\n**Date:** \n**Attendees:** \n**Facilitator:** \n\n## Agenda\n1. \n2. \n3. \n\n## Discussion\n\n\n## Action Items\n- [ ] \n- [ ] \n\n## Next Steps\n\n",
        },
        {
            "template_id": "tpl_decision_log",
            "name": "Decision Log",
            "icon": "",
            "content": "# Decision Log\n\n## Decision\n**What was decided:** \n\n## Context\n**Background:** \n\n## Options Considered\n1. **Option A:** \n2. **Option B:** \n3. **Option C:** \n\n## Rationale\n**Why this decision:** \n\n## Impact\n**Who is affected:** \n**Timeline:** \n\n## Follow-up\n- [ ] \n",
        },
        {
            "template_id": "tpl_runbook",
            "name": "Runbook",
            "icon": "",
            "content": "# Runbook: [Service Name]\n\n## Overview\n**Service:** \n**Owner:** \n**Criticality:** High / Medium / Low\n\n## Prerequisites\n- \n- \n\n## Steps\n\n### 1. Check Status\n```bash\n# Command to check status\n```\n\n### 2. Restart Service\n```bash\n# Command to restart\n```\n\n### 3. Verify\n```bash\n# Command to verify\n```\n\n## Troubleshooting\n| Symptom | Cause | Fix |\n|---------|-------|-----|\n| | | |\n\n## Escalation\n- **Level 1:** \n- **Level 2:** \n",
        },
        {
            "template_id": "tpl_api_docs",
            "name": "API Documentation",
            "icon": "",
            "content": "# API Documentation\n\n## Base URL\n`https://api.example.com/v1`\n\n## Authentication\nAll requests require a Bearer token in the Authorization header.\n\n## Endpoints\n\n### GET /resource\n**Description:** List all resources\n\n**Headers:**\n| Header | Value |\n|--------|-------|\n| Authorization | Bearer {token} |\n\n**Response:**\n```json\n{\n  \"data\": [],\n  \"total\": 0\n}\n```\n\n### POST /resource\n**Description:** Create a resource\n\n**Body:**\n```json\n{\n  \"name\": \"string\",\n  \"description\": \"string\"\n}\n```\n\n## Error Codes\n| Code | Description |\n|------|-------------|\n| 400 | Bad Request |\n| 401 | Unauthorized |\n| 404 | Not Found |\n| 500 | Server Error |\n",
        },
    ]

    @api_router.get("/wiki-templates")
    async def get_wiki_templates(request: Request):
        await get_current_user(request)
        return {"templates": [{"template_id": t["template_id"], "name": t["name"], "icon": t["icon"]} for t in WIKI_TEMPLATES]}

    @api_router.post("/workspaces/{workspace_id}/wiki/from-template")
    async def create_wiki_from_template(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        template_id = body.get("template_id", "")
        custom_title = body.get("title", "")
        template = next((t for t in WIKI_TEMPLATES if t["template_id"] == template_id), None)
        if not template:
            raise HTTPException(404, "Template not found")
        title = custom_title or template["name"]
        now = now_iso()
        page_id = f"wp_{uuid.uuid4().hex[:12]}"
        content = template["content"]
        await db.wiki_pages.insert_one({
            "page_id": page_id, "workspace_id": workspace_id, "title": title,
            "content": content, "parent_id": body.get("parent_id"),
            "icon": template["icon"], "pinned": False,
            "word_count": len(content.split()), "version": 1,
            "created_by": user["user_id"], "created_by_name": user.get("name", "Unknown"),
            "updated_by": user["user_id"], "updated_by_name": user.get("name", "Unknown"),
            "created_at": now, "updated_at": now, "is_deleted": False,
        })
        await db.wiki_versions.insert_one({
            "version_id": f"wv_{uuid.uuid4().hex[:12]}", "page_id": page_id,
            "version": 1, "title": title, "content": content,
            "author_id": user["user_id"], "author_name": user.get("name", "Unknown"),
            "created_at": now,
        })
        result = await db.wiki_pages.find_one({"page_id": page_id}, {"_id": 0})
        return result

    # ============ Unified Search ============

    @api_router.get("/workspaces/{workspace_id}/search")
    async def unified_search(workspace_id: str, request: Request, q: str = "", limit: int = 30):
        """Search across messages, tasks, wiki, code repo"""
        user = await _authed_user(request, workspace_id)
        if not q.strip():
            return {"results": [], "total": 0}
        regex = {"$regex": safe_regex(q), "$options": "i"}
        results = []
        # Search messages
        channels = await db.channels.find({"workspace_id": workspace_id}, {"_id": 0, "channel_id": 1}).to_list(50)
        ch_ids = [c["channel_id"] for c in channels]
        if ch_ids:
            msgs = await db.messages.find(
                {"channel_id": {"$in": ch_ids}, "content": regex},
                {"_id": 0, "message_id": 1, "content": 1, "sender_name": 1, "channel_id": 1, "created_at": 1}
            ).sort("created_at", -1).limit(10).to_list(10)
            for m in msgs:
                results.append({"type": "message", "id": m["message_id"], "title": m.get("sender_name", ""), "snippet": m["content"][:200], "meta": m.get("channel_id", ""), "date": m.get("created_at")})
        # Search tasks
        tasks_ws = await db.tasks.find(
            {"workspace_id": workspace_id, "$or": [{"title": regex}, {"description": regex}]},
            {"_id": 0, "task_id": 1, "title": 1, "status": 1, "description": 1}
        ).limit(10).to_list(10)
        for t in tasks_ws:
            results.append({"type": "task", "id": t["task_id"], "title": t["title"], "snippet": t.get("description", "")[:200], "meta": t.get("status", ""), "date": None})
        # Search project tasks
        projects = await db.projects.find({"workspace_id": workspace_id}, {"_id": 0, "project_id": 1}).to_list(50)
        p_ids = [p["project_id"] for p in projects]
        if p_ids:
            ptasks = await db.project_tasks.find(
                {"project_id": {"$in": p_ids}, "$or": [{"title": regex}, {"description": regex}]},
                {"_id": 0, "task_id": 1, "title": 1, "status": 1, "description": 1}
            ).limit(10).to_list(10)
            for t in ptasks:
                results.append({"type": "task", "id": t["task_id"], "title": t["title"], "snippet": t.get("description", "")[:200], "meta": t.get("status", ""), "date": None})
        # Search wiki
        wiki = await db.wiki_pages.find(
            {"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "$or": [{"title": regex}, {"content": regex}]},
            {"_id": 0, "page_id": 1, "title": 1, "content": 1, "updated_at": 1}
        ).limit(10).to_list(10)
        for w in wiki:
            results.append({"type": "wiki", "id": w["page_id"], "title": w["title"], "snippet": w.get("content", "")[:200], "meta": "docs", "date": w.get("updated_at")})
        # Search code repo
        code = await db.repo_files.find(
            {"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "$or": [{"path": regex}, {"content": regex}]},
            {"_id": 0, "file_id": 1, "path": 1, "content": 1, "language": 1}
        ).limit(10).to_list(10)
        for c in code:
            results.append({"type": "code", "id": c["file_id"], "title": c["path"], "snippet": c.get("content", "")[:200], "meta": c.get("language", ""), "date": None})
        return {"results": results[:limit], "total": len(results)}

    # Presence tracking endpoints are in routes_tier23.py
    # Webhook endpoints are in routes_webhooks.py


    # ============ Workspace Activities (for AI Agent Action Panel) ============

    @api_router.get("/workspaces/{workspace_id}/activities")
    async def get_workspace_activities(workspace_id: str, request: Request, channel_id: str = None, 
                                        action_type: str = None, agent: str = None, limit: int = 50):
        """Get recent AI agent activities across workspace modules"""
        user = await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if channel_id:
            query["channel_id"] = channel_id
        if action_type:
            query["action_type"] = action_type
        if agent:
            query["$or"] = [{"agent": agent}, {"agent_key": agent}]
        activities = await db.workspace_activities.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        total = await db.workspace_activities.count_documents(query)
        return {"activities": activities, "total": total}

    @api_router.get("/workspaces/{workspace_id}/activities/export")
    async def export_workspace_activities(workspace_id: str, request: Request, format: str = "json"):
        """Export all activities as JSON or CSV"""
        user = await _authed_user(request, workspace_id)
        activities = await db.workspace_activities.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(500)

        if format == "csv":
            import csv, io
            output = io.StringIO()
            if activities:
                writer = csv.DictWriter(output, fieldnames=["timestamp", "agent", "action_type", "module", "tool", "status", "summary"])
                writer.writeheader()
                for a in activities:
                    writer.writerow({k: str(a.get(k, ""))[:200] for k in ["timestamp", "agent", "action_type", "module", "tool", "status", "summary"]})
            from fastapi.responses import Response as RawResponse
            return RawResponse(content=output.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=activities_{workspace_id}.csv"})

        return {"activities": activities, "total": len(activities)}
