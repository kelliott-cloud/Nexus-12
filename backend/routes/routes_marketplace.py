"""Marketplace & Artifacts API routes"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso
from nexus_utils import safe_regex


# ============ Models ============

class PublishTemplate(BaseModel):
    workflow_id: str
    name: str = Field(..., min_length=1)
    description: str = ""
    category: str = "general"
    difficulty: str = "intermediate"
    estimated_time: str = ""
    scope: str = "global"  # "global" or "org"
    org_id: Optional[str] = None

class RateTemplate(BaseModel):
    rating: int = Field(..., ge=1, le=5)

class ArtifactCreate(BaseModel):
    name: str = Field(..., min_length=1)
    content: str = ""
    content_type: str = "text"  # text, json, code, markdown, image
    workflow_id: Optional[str] = None
    run_id: Optional[str] = None
    node_id: Optional[str] = None
    tags: List[str] = []
    file_url: Optional[str] = None  # URL or path to attached file
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None

class ArtifactUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None

class ArtifactTag(BaseModel):
    tags: List[str]


VALID_CATEGORIES = ["research", "content", "development", "business", "general", "data", "marketing", "operations"]


def register_marketplace_routes(api_router, db, get_current_user):

    # ============ MARKETPLACE ============

    @api_router.get("/marketplace")
    async def browse_marketplace(
        request: Request,
        category: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "popular",
        limit: int = 20,
        offset: int = 0,
    ):
        """Browse global marketplace templates"""
        await get_current_user(request)
        query = {"scope": "global", "is_active": True}
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": safe_regex(search), "$options": "i"}},
                {"description": {"$regex": safe_regex(search), "$options": "i"}},
            ]

        sort_field = "usage_count" if sort == "popular" else "avg_rating" if sort == "rating" else "created_at"
        sort_dir = -1

        templates = await db.marketplace_templates.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(offset).limit(limit).to_list(limit)
        total = await db.marketplace_templates.count_documents(query)
        return {"templates": templates, "total": total}

    @api_router.get("/marketplace/org/{org_id}")
    async def browse_org_marketplace(
        org_id: str, request: Request,
        category: Optional[str] = None, search: Optional[str] = None,
        limit: int = 20, offset: int = 0,
    ):
        """Browse org-scoped marketplace templates"""
        await get_current_user(request)
        query = {"org_id": org_id, "scope": "org", "is_active": True}
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": safe_regex(search), "$options": "i"}},
                {"description": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        templates = await db.marketplace_templates.find(query, {"_id": 0}).sort("usage_count", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.marketplace_templates.count_documents(query)
        return {"templates": templates, "total": total}

    @api_router.get("/marketplace/{template_id}")
    async def get_marketplace_template(template_id: str, request: Request):
        await get_current_user(request)
        tpl = await db.marketplace_templates.find_one({"marketplace_id": template_id, "is_active": True}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")
        return tpl

    @api_router.post("/marketplace/publish")
    async def publish_to_marketplace(data: PublishTemplate, request: Request):
        """Publish a workflow as a marketplace template"""
        user = await get_current_user(request)
        # Get the workflow with its nodes and edges
        wf = await db.workflows.find_one({"workflow_id": data.workflow_id}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        nodes = await db.workflow_nodes.find({"workflow_id": data.workflow_id}, {"_id": 0}).to_list(100)
        edges = await db.workflow_edges.find({"workflow_id": data.workflow_id}, {"_id": 0}).to_list(200)

        if len(nodes) == 0:
            raise HTTPException(400, "Cannot publish an empty workflow")

        marketplace_id = f"mkt_{uuid.uuid4().hex[:12]}"
        template = {
            "marketplace_id": marketplace_id,
            "publisher_id": user["user_id"],
            "publisher_name": user.get("name", user.get("email", "Anonymous")),
            "name": data.name,
            "description": data.description,
            "category": data.category if data.category in VALID_CATEGORIES else "general",
            "difficulty": data.difficulty,
            "estimated_time": data.estimated_time,
            "scope": data.scope,
            "org_id": data.org_id if data.scope == "org" else None,
            "is_active": True,
            "nodes": [{k: v for k, v in n.items() if k not in ("_id", "workflow_id")} for n in nodes],
            "edges": [{k: v for k, v in e.items() if k not in ("_id", "workflow_id")} for e in edges],
            "node_count": len(nodes),
            "edge_count": len(edges),
            "input_schema": {},
            "usage_count": 0,
            "avg_rating": 0,
            "rating_count": 0,
            "ratings_sum": 0,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        # Extract input schema from input nodes
        input_nodes = [n for n in nodes if n.get("type") == "input"]
        if input_nodes and input_nodes[0].get("input_schema"):
            template["input_schema"] = input_nodes[0]["input_schema"]

        await db.marketplace_templates.insert_one(template)
        return {k: v for k, v in template.items() if k != "_id"}

    @api_router.post("/marketplace/{template_id}/import")
    async def import_from_marketplace(template_id: str, request: Request, workspace_id: Optional[str] = None):
        """Import a marketplace template into a workspace as a new workflow"""
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        tpl = await db.marketplace_templates.find_one({"marketplace_id": template_id, "is_active": True}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")

        if not workspace_id:
            raise HTTPException(400, "workspace_id is required")

        # Create the workflow
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        workflow = {
            "workflow_id": workflow_id,
            "workspace_id": workspace_id,
            "name": tpl["name"],
            "description": tpl["description"],
            "status": "draft",
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.workflows.insert_one(workflow)

        # Create nodes
        node_id_map = {}
        nodes_created = []
        for n in tpl.get("nodes") or []:
            new_node_id = f"wn_{uuid.uuid4().hex[:12]}"
            old_id = n.get("node_id", n.get("id", ""))
            node_id_map[old_id] = new_node_id
            if n.get("label"):
                node_id_map[n["label"]] = new_node_id
            node = {
                "node_id": new_node_id, "workflow_id": workflow_id,
                "type": n.get("type", "ai_agent"), "label": n.get("label", "Node"),
                "position": n.get("position", 0),
                "ai_model": n.get("ai_model"), "system_prompt": n.get("system_prompt"),
                "user_prompt_template": n.get("user_prompt_template"),
                "temperature": n.get("temperature", 0.7), "max_tokens": n.get("max_tokens", 4096),
                "input_schema": n.get("input_schema") or {}, "output_schema": n.get("output_schema") or {},
                "condition_logic": n.get("condition_logic"),
                "timeout_seconds": n.get("timeout_seconds", 120),
                "retry_count": n.get("retry_count", 1),
                "position_x": n.get("position_x", 250), "position_y": n.get("position_y", 0),
                "created_at": now,
            }
            await db.workflow_nodes.insert_one(node)
            nodes_created.append({k: v for k, v in node.items() if k != "_id"})

        # Create edges
        edges_created = []
        for e in tpl.get("edges") or []:
            src_key = e.get("source_node_id", e.get("source", ""))
            tgt_key = e.get("target_node_id", e.get("target", ""))
            src_id = node_id_map.get(src_key)
            tgt_id = node_id_map.get(tgt_key)
            if src_id and tgt_id:
                edge_id = f"we_{uuid.uuid4().hex[:12]}"
                edge = {
                    "edge_id": edge_id, "workflow_id": workflow_id,
                    "source_node_id": src_id, "target_node_id": tgt_id,
                    "edge_type": e.get("edge_type", "default"),
                    "label": e.get("label"), "created_at": now,
                }
                await db.workflow_edges.insert_one(edge)
                edges_created.append({k: v for k, v in edge.items() if k != "_id"})

        # Increment usage count
        await db.marketplace_templates.update_one(
            {"marketplace_id": template_id}, {"$inc": {"usage_count": 1}}
        )

        result = {**{k: v for k, v in workflow.items() if k != "_id"}, "nodes": nodes_created, "edges": edges_created}
        return result

    @api_router.post("/marketplace/{template_id}/rate")
    async def rate_marketplace_template(template_id: str, data: RateTemplate, request: Request):
        user = await get_current_user(request)
        tpl = await db.marketplace_templates.find_one({"marketplace_id": template_id}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")
        # Check if user already rated
        existing = await db.marketplace_ratings.find_one(
            {"marketplace_id": template_id, "user_id": user["user_id"]}
        )
        if existing:
            old_rating = existing["rating"]
            await db.marketplace_ratings.update_one(
                {"marketplace_id": template_id, "user_id": user["user_id"]},
                {"$set": {"rating": data.rating, "updated_at": now_iso()}}
            )
            await db.marketplace_templates.update_one(
                {"marketplace_id": template_id},
                {"$inc": {"ratings_sum": data.rating - old_rating}}
            )
        else:
            await db.marketplace_ratings.insert_one({
                "marketplace_id": template_id, "user_id": user["user_id"],
                "rating": data.rating, "created_at": now_iso(),
            })
            await db.marketplace_templates.update_one(
                {"marketplace_id": template_id},
                {"$inc": {"rating_count": 1, "ratings_sum": data.rating}}
            )
        # Recalculate avg
        updated = await db.marketplace_templates.find_one({"marketplace_id": template_id}, {"_id": 0})
        if updated:
            avg = updated["ratings_sum"] / max(updated["rating_count"], 1)
            await db.marketplace_templates.update_one(
                {"marketplace_id": template_id}, {"$set": {"avg_rating": round(avg, 1)}}
        )
        return {"avg_rating": round(avg, 1), "rating_count": updated["rating_count"]}

    # ============ ARTIFACTS ============

    @api_router.post("/workspaces/{workspace_id}/artifacts")
    async def create_artifact(workspace_id: str, data: ArtifactCreate, request: Request):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        artifact = {
            "artifact_id": artifact_id,
            "workspace_id": workspace_id,
            "name": data.name,
            "content": data.content,
            "content_type": data.content_type,
            "workflow_id": data.workflow_id,
            "run_id": data.run_id,
            "node_id": data.node_id,
            "tags": data.tags,
            "pinned": False,
            "version": 1,
            "file_url": data.file_url,
            "file_name": data.file_name,
            "file_size": data.file_size,
            "mime_type": data.mime_type,
            "attachments": [],
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.artifacts.insert_one(artifact)
        # Store version history
        await db.artifact_versions.insert_one({
            "artifact_id": artifact_id, "version": 1,
            "content": data.content, "created_by": user["user_id"], "created_at": now,
        })
        return {k: v for k, v in artifact.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/artifacts")
    async def list_artifacts(
        workspace_id: str, request: Request,
        search: Optional[str] = None, tag: Optional[str] = None,
        pinned: Optional[bool] = None, content_type: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ):
        await get_current_user(request)
        query = {"workspace_id": workspace_id}
        if search:
            query["$or"] = [
                {"name": {"$regex": safe_regex(search), "$options": "i"}},
                {"tags": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        if tag:
            query["tags"] = tag
        if pinned is not None:
            query["pinned"] = pinned
        if content_type:
            query["content_type"] = content_type

        artifacts = await db.artifacts.find(query, {"_id": 0}).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.artifacts.count_documents(query)
        return {"artifacts": artifacts, "total": total}

    @api_router.get("/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str, request: Request):
        await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if not artifact:
            raise HTTPException(404, "Artifact not found")
        versions = await db.artifact_versions.find(
            {"artifact_id": artifact_id}, {"_id": 0}
        ).sort("version", -1).to_list(50)
        artifact["versions"] = versions
        return artifact

    @api_router.put("/artifacts/{artifact_id}")
    async def update_artifact(artifact_id: str, data: ArtifactUpdate, request: Request):
        user = await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if not artifact:
            raise HTTPException(404, "Artifact not found")

        updates = {"updated_at": now_iso()}
        new_version = False
        if data.name is not None:
            updates["name"] = data.name
        if data.tags is not None:
            updates["tags"] = data.tags
        if data.content is not None:
            updates["content"] = data.content
            updates["version"] = artifact["version"] + 1
            new_version = True

        await db.artifacts.update_one({"artifact_id": artifact_id}, {"$set": updates})

        if new_version:
            # Calculate change summary
            old_content = artifact.get("content", "")
            new_content = data.content
            old_lines = len(old_content.splitlines())
            new_lines = len(new_content.splitlines())
            await db.artifact_versions.insert_one({
                "artifact_id": artifact_id, "version": updates["version"],
                "content": data.content, "created_by": user["user_id"],
                "created_at": now_iso(),
                "change_summary": {
                    "lines_before": old_lines,
                    "lines_after": new_lines,
                    "chars_added": max(0, len(new_content) - len(old_content)),
                    "chars_removed": max(0, len(old_content) - len(new_content)),
                },
            })

        return await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})

    @api_router.post("/artifacts/{artifact_id}/pin")
    async def toggle_pin_artifact(artifact_id: str, request: Request):
        await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if not artifact:
            raise HTTPException(404, "Artifact not found")
        new_pinned = not artifact.get("pinned", False)
        await db.artifacts.update_one({"artifact_id": artifact_id}, {"$set": {"pinned": new_pinned}})
        return {"pinned": new_pinned}

    @api_router.post("/artifacts/{artifact_id}/tag")
    async def tag_artifact(artifact_id: str, data: ArtifactTag, request: Request):
        await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if not artifact:
            raise HTTPException(404, "Artifact not found")
        existing_tags = set(artifact.get("tags") or [])
        existing_tags.update(data.tags)
        await db.artifacts.update_one(
            {"artifact_id": artifact_id}, {"$set": {"tags": list(existing_tags)}}
        )
        return {"tags": list(existing_tags)}

    @api_router.delete("/artifacts/{artifact_id}")
    async def delete_artifact(artifact_id: str, request: Request):
        await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id})
        if not artifact:
            raise HTTPException(404, "Artifact not found")
        await db.artifacts.delete_one({"artifact_id": artifact_id})
        await db.artifact_versions.delete_many({"artifact_id": artifact_id})
        return {"message": "Artifact deleted"}

    @api_router.post("/artifacts/{artifact_id}/restore/{version}")
    async def restore_artifact_version(artifact_id: str, version: int, request: Request):
        """Restore an artifact to a specific version"""
        user = await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if not artifact:
            raise HTTPException(404, "Artifact not found")
        target = await db.artifact_versions.find_one(
            {"artifact_id": artifact_id, "version": version}, {"_id": 0}
        )
        if not target:
            raise HTTPException(404, f"Version {version} not found")
        new_ver = artifact["version"] + 1
        now = now_iso()
        await db.artifacts.update_one(
            {"artifact_id": artifact_id},
            {"$set": {"content": target["content"], "version": new_ver, "updated_at": now}}
        )
        await db.artifact_versions.insert_one({
            "artifact_id": artifact_id, "version": new_ver,
            "content": target["content"], "created_by": user["user_id"],
            "created_at": now, "restored_from": version,
        })
        return await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})

    @api_router.get("/artifacts/{artifact_id}/diff")
    async def get_artifact_diff(artifact_id: str, request: Request, v1: int = 0, v2: int = 0):
        """Get diff between two artifact versions"""
        await get_current_user(request)
        ver1 = await db.artifact_versions.find_one(
            {"artifact_id": artifact_id, "version": v1}, {"_id": 0}
        )
        ver2 = await db.artifact_versions.find_one(
            {"artifact_id": artifact_id, "version": v2}, {"_id": 0}
        )
        if not ver1 or not ver2:
            raise HTTPException(404, "One or both versions not found")
        import difflib
        lines1 = (ver1.get("content") or "").splitlines(keepends=True)
        lines2 = (ver2.get("content") or "").splitlines(keepends=True)
        diff = list(difflib.unified_diff(lines1, lines2, fromfile=f"v{v1}", tofile=f"v{v2}"))
        additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        return {
            "diff": "".join(diff),
            "additions": additions,
            "deletions": deletions,
            "v1": {"version": v1, "created_at": ver1.get("created_at"), "created_by": ver1.get("created_by")},
            "v2": {"version": v2, "created_at": ver2.get("created_at"), "created_by": ver2.get("created_by")},
        }

    @api_router.post("/artifacts/{artifact_id}/attachments")
    async def add_artifact_attachment(artifact_id: str, request: Request):
        """Add a file attachment to an artifact"""
        user = await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if not artifact:
            raise HTTPException(404, "Artifact not found")

        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file provided")

        import base64
        content_bytes = await file.read()
        file_b64 = base64.b64encode(content_bytes).decode("utf-8")

        attachment = {
            "attachment_id": f"att_{uuid.uuid4().hex[:8]}",
            "filename": file.filename or "attachment",
            "mime_type": file.content_type or "application/octet-stream",
            "size": len(content_bytes),
            "data": file_b64,
            "uploaded_by": user["user_id"],
            "uploaded_at": now_iso(),
        }

        await db.artifact_attachments.insert_one({
            "artifact_id": artifact_id,
            **attachment,
        })

        # Update artifact's attachment list (without data for listing)
        att_ref = {k: v for k, v in attachment.items() if k != "data"}
        await db.artifacts.update_one(
            {"artifact_id": artifact_id},
            {"$push": {"attachments": att_ref}, "$set": {"updated_at": now_iso()}}
        )

        return att_ref

    @api_router.get("/artifacts/{artifact_id}/attachments/{attachment_id}")
    async def get_artifact_attachment(artifact_id: str, attachment_id: str, request: Request):
        """Get attachment data (base64)"""
        await get_current_user(request)
        att = await db.artifact_attachments.find_one(
            {"artifact_id": artifact_id, "attachment_id": attachment_id}, {"_id": 0}
        )
        if not att:
            raise HTTPException(404, "Attachment not found")
        return att

    @api_router.delete("/artifacts/{artifact_id}/attachments/{attachment_id}")
    async def delete_artifact_attachment(artifact_id: str, attachment_id: str, request: Request):
        """Delete an attachment"""
        await get_current_user(request)
        await db.artifact_attachments.delete_one({"artifact_id": artifact_id, "attachment_id": attachment_id})
        await db.artifacts.update_one(
            {"artifact_id": artifact_id},
            {"$pull": {"attachments": {"attachment_id": attachment_id}}}
        )
        return {"message": "Attachment deleted"}

