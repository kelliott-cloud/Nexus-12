"""Global Search — Cross-entity search across messages, projects, tasks, wiki, artifacts.
All queries are scoped to the user's workspace memberships for security.
"""
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


from nexus_utils import safe_regex

def register_global_search_routes(api_router, db, get_current_user):

    @api_router.get("/search")
    async def global_search(request: Request, q: str = "", types: str = "", limit: int = 20):
        user = await get_current_user(request)
        if not q.strip():
            return {"results": [], "query": q}

        # === SECURITY: Get user's workspace memberships ===
        user_id = user["user_id"]
        memberships = await db.workspace_members.find(
            {"user_id": user_id}, {"_id": 0, "workspace_id": 1}
        ).to_list(100)
        user_workspace_ids = [m["workspace_id"] for m in memberships]

        # Also include workspaces the user owns
        owned = await db.workspaces.find(
            {"owner_id": user_id}, {"_id": 0, "workspace_id": 1}
        ).to_list(100)
        user_workspace_ids.extend([w["workspace_id"] for w in owned])
        user_workspace_ids = list(set(user_workspace_ids))

        if not user_workspace_ids:
            return {"results": [], "query": q, "total": 0}

        # Get channels in user's workspaces (for message scoping)
        user_channels = await db.channels.find(
            {"workspace_id": {"$in": user_workspace_ids}}, {"_id": 0, "channel_id": 1}
        ).to_list(500)
        user_channel_ids = [c["channel_id"] for c in user_channels]

        search_types = types.split(",") if types else ["messages", "projects", "tasks", "wiki", "artifacts"]
        results = []
        regex = {"$regex": safe_regex(q), "$options": "i"}

        if "messages" in search_types and user_channel_ids:
            msgs = await db.messages.find(
                {"content": regex, "channel_id": {"$in": user_channel_ids}},
                {"_id": 0, "message_id": 1, "channel_id": 1, "sender_name": 1, "content": 1, "created_at": 1}
            ).sort("created_at", -1).limit(limit).to_list(limit)
            for m in msgs:
                results.append({"type": "message", "id": m.get("message_id"), "title": m.get("sender_name", "?"), "snippet": m.get("content", "")[:200], "channel_id": m.get("channel_id"), "date": m.get("created_at")})

        if "projects" in search_types:
            projs = await db.projects.find(
                {"$or": [{"name": regex}, {"description": regex}], "workspace_id": {"$in": user_workspace_ids}},
                {"_id": 0, "project_id": 1, "name": 1, "description": 1, "status": 1, "workspace_id": 1}
            ).limit(limit).to_list(limit)
            for p in projs:
                results.append({"type": "project", "id": p.get("project_id"), "title": p.get("name"), "snippet": p.get("description", "")[:200], "workspace_id": p.get("workspace_id"), "status": p.get("status")})

        if "tasks" in search_types:
            user_projects = await db.projects.find(
                {"workspace_id": {"$in": user_workspace_ids}}, {"_id": 0, "project_id": 1}
            ).to_list(500)
            user_project_ids = [p["project_id"] for p in user_projects]
            if user_project_ids:
                tasks = await db.project_tasks.find(
                    {"$or": [{"title": regex}, {"description": regex}], "project_id": {"$in": user_project_ids}},
                    {"_id": 0, "task_id": 1, "title": 1, "status": 1, "project_id": 1}
                ).limit(limit).to_list(limit)
                for t in tasks:
                    results.append({"type": "task", "id": t.get("task_id"), "title": t.get("title"), "snippet": "Status: " + t.get("status", "?"), "project_id": t.get("project_id")})

        if "wiki" in search_types:
            pages = await db.wiki_pages.find(
                {"$or": [{"title": regex}, {"content": regex}], "workspace_id": {"$in": user_workspace_ids}},
                {"_id": 0, "page_id": 1, "title": 1, "content": 1}
            ).limit(limit).to_list(limit)
            for p in pages:
                results.append({"type": "wiki", "id": p.get("page_id"), "title": p.get("title"), "snippet": p.get("content", "")[:200]})

        if "artifacts" in search_types:
            arts = await db.artifacts.find(
                {"$or": [{"name": regex}, {"content": regex}], "workspace_id": {"$in": user_workspace_ids}},
                {"_id": 0, "artifact_id": 1, "name": 1, "content_type": 1}
            ).limit(limit).to_list(limit)
            for a in arts:
                results.append({"type": "artifact", "id": a.get("artifact_id"), "title": a.get("name"), "snippet": a.get("content_type", "")})

        results.sort(key=lambda x: x.get("date", ""), reverse=True)
        return {"results": results[:limit], "query": q, "total": len(results)}
