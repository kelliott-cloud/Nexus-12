from nexus_utils import now_iso
"""Workspace Deletion — Bulk delete for super admins, org admins, and individual owners.

Cascade deletes all related data: channels, messages, projects, tasks, files, etc.
Supports single and multi-select deletion with confirmation.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



# Collections to cascade-delete when a workspace is removed
CASCADE_COLLECTIONS = [
    "channels", "messages", "projects", "project_tasks", "milestones",
    "task_relationships", "code_repo_files", "code_repo_branches",
    "wiki_pages", "file_storage", "ideation_boards", "activity_logs",
    "context_ledger", "recycle_bin", "duplicate_overrides", "file_locks",
    "crdt_documents", "artifacts", "artifact_versions", "directives",
    "workspace_members", "workspace_memory", "work_queue",
    "deployments", "deployment_runs", "deployment_action_log",
    "deployment_webhooks", "deployment_schedules",
    "reporting_events", "reporting_rollups_daily",
    "nexus_connections", "workspace_budgets", "agent_memory",
    "agent_skills", "decision_log", "channel_summaries",
    "arena_battles", "arena_leaderboard", "prompt_library",
    "disagreements", "agent_requests",
]


def register_workspace_deletion_routes(api_router, db, get_current_user):

    async def _check_permission(user, workspace):
        """Check if user can delete this workspace."""
        role = user.get("platform_role", "")
        
        # Super admin can delete any workspace
        if role == "super_admin":
            return True
        
        # Workspace owner can delete their own
        if workspace.get("owner_id") == user["user_id"]:
            return True
        
        # Org admin can delete workspaces in their org
        if workspace.get("org_id"):
            org_member = await db.org_members.find_one(
                {"org_id": workspace["org_id"], "user_id": user["user_id"]},
                {"_id": 0, "role": 1}
            )
            if org_member and org_member.get("role") in ("admin", "owner"):
                return True
        
        return False

    async def _cascade_delete(workspace_id):
        """Delete all data associated with a workspace."""
        deleted_counts = {}
        for collection_name in CASCADE_COLLECTIONS:
            try:
                collection = db[collection_name]
                # Try workspace_id first, then fallback patterns
                result = await collection.delete_many({"workspace_id": workspace_id})
                if result.deleted_count > 0:
                    deleted_counts[collection_name] = result.deleted_count
            except Exception as e:
                logger.debug(f"Cascade delete {collection_name}: {e}")
        
        # Delete channel-scoped data (messages are keyed by channel_id, not workspace_id)
        channels = await db.channels.find(
            {"workspace_id": workspace_id}, {"_id": 0, "channel_id": 1}
        ).to_list(100)
        channel_ids = [c["channel_id"] for c in channels]
        if channel_ids:
            msg_result = await db.messages.delete_many({"channel_id": {"$in": channel_ids}})
            if msg_result.deleted_count > 0:
                deleted_counts["messages"] = deleted_counts.get("messages", 0) + msg_result.deleted_count
        
        # Delete the workspace itself
        await db.workspaces.delete_one({"workspace_id": workspace_id})
        
        return deleted_counts

    # ============ Single Workspace Delete ============

    @api_router.delete("/workspaces/{ws_id}")
    async def delete_workspace(ws_id: str, request: Request):
        """Delete a workspace and all its data. Requires owner, org admin, or super admin."""
        user = await get_current_user(request)
        
        workspace = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        if not await _check_permission(user, workspace):
            raise HTTPException(403, "You don't have permission to delete this workspace")
        
        deleted = await _cascade_delete(ws_id)
        
        # Audit log
        await db.activity_logs.insert_one({
            "log_id": f"log_{uuid.uuid4().hex[:12]}",
            "action": "workspace_deleted",
            "workspace_id": ws_id,
            "workspace_name": workspace.get("name", ""),
            "user_id": user["user_id"],
            "user_name": user.get("name", ""),
            "details": {"deleted_counts": deleted},
            "created_at": now_iso(),
        })
        
        logger.info(f"Workspace {ws_id} ({workspace.get('name','')}) deleted by {user['user_id']} — {sum(deleted.values())} records removed")
        
        return {
            "message": f"Workspace '{workspace.get('name', '')}' permanently deleted",
            "workspace_id": ws_id,
            "deleted_counts": deleted,
            "total_records_removed": sum(deleted.values()),
        }

    # ============ Bulk Delete ============

    @api_router.post("/workspaces/bulk-delete")
    async def bulk_delete_workspaces(request: Request):
        """Delete multiple workspaces at once. Each workspace is permission-checked individually."""
        user = await get_current_user(request)
        body = await request.json()
        workspace_ids = body.get("workspace_ids") or []
        
        if not workspace_ids:
            raise HTTPException(400, "No workspace IDs provided")
        if len(workspace_ids) > 50:
            raise HTTPException(400, "Maximum 50 workspaces per bulk delete")
        
        results = []
        for ws_id in workspace_ids:
            workspace = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
            if not workspace:
                results.append({"workspace_id": ws_id, "status": "not_found"})
                continue
            
            if not await _check_permission(user, workspace):
                results.append({"workspace_id": ws_id, "name": workspace.get("name", ""), "status": "permission_denied"})
                continue
            
            deleted = await _cascade_delete(ws_id)
            results.append({
                "workspace_id": ws_id,
                "name": workspace.get("name", ""),
                "status": "deleted",
                "records_removed": sum(deleted.values()),
            })
        
        # Audit log
        deleted_count = sum(1 for r in results if r["status"] == "deleted")
        await db.activity_logs.insert_one({
            "log_id": f"log_{uuid.uuid4().hex[:12]}",
            "action": "bulk_workspace_delete",
            "user_id": user["user_id"],
            "user_name": user.get("name", ""),
            "details": {"requested": len(workspace_ids), "deleted": deleted_count, "results": results},
            "created_at": now_iso(),
        })
        
        logger.info(f"Bulk delete: {deleted_count}/{len(workspace_ids)} workspaces deleted by {user['user_id']}")
        
        return {
            "total_requested": len(workspace_ids),
            "deleted": deleted_count,
            "results": results,
        }

    # ============ Pre-Delete Info (show what will be deleted) ============

    @api_router.get("/workspaces/{ws_id}/delete-preview")
    async def delete_preview(ws_id: str, request: Request):
        """Preview what will be deleted — shows counts of all related data."""
        user = await get_current_user(request)
        
        workspace = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        if not await _check_permission(user, workspace):
            raise HTTPException(403, "No permission")
        
        counts = {}
        counts["channels"] = await db.channels.count_documents({"workspace_id": ws_id})
        counts["projects"] = await db.projects.count_documents({"workspace_id": ws_id})
        counts["tasks"] = await db.project_tasks.count_documents({"workspace_id": ws_id})
        counts["files"] = await db.code_repo_files.count_documents({"workspace_id": ws_id})
        counts["deployments"] = await db.deployments.count_documents({"workspace_id": ws_id})
        
        # Count messages across all channels
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0, "channel_id": 1}).to_list(100)
        ch_ids = [c["channel_id"] for c in channels]
        counts["messages"] = await db.messages.count_documents({"channel_id": {"$in": ch_ids}}) if ch_ids else 0
        
        return {
            "workspace_id": ws_id,
            "workspace_name": workspace.get("name", ""),
            "owner_id": workspace.get("owner_id", ""),
            "can_delete": True,
            "data_counts": counts,
            "total_records": sum(counts.values()),
            "warning": "This action is permanent and cannot be undone.",
        }
