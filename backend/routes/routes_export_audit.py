"""Export & Audit Trail — export conversations/workflows/artifacts + audit logging"""
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuditEntry(BaseModel):
    action: str
    resource_type: str
    resource_id: str = ""
    details: dict = {}


def register_export_audit_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Audit Trail ============

    async def log_audit(db_ref, user_id, action, resource_type, resource_id="", details=None, workspace_id=""):
        """Helper to log an audit entry"""
        await db_ref.audit_log.insert_one({
            "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "workspace_id": workspace_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @api_router.get("/workspaces/{workspace_id}/audit-log")
    async def get_audit_log(
        workspace_id: str, request: Request,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ):
        """Get audit log for a workspace"""
        await get_current_user(request)
        query = {"workspace_id": workspace_id}
        if action:
            query["action"] = action
        if resource_type:
            query["resource_type"] = resource_type
        entries = await db.audit_log.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.audit_log.count_documents(query)

        # Enrich with user names
        if entries:
            uids = list({e["user_id"] for e in entries if e.get("user_id")})
            users = await db.users.find({"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(50)
            umap = {u["user_id"]: u["name"] for u in users}
            for e in entries:
                e["user_name"] = umap.get(e.get("user_id"), "System")

        return {"entries": entries, "total": total}

    @api_router.get("/audit-log/actions")
    async def get_audit_actions(request: Request):
        """Get available audit action types"""
        await get_current_user(request)
        return {"actions": [
            "create", "update", "delete", "login", "logout", "export",
            "run_workflow", "approve_gate", "reject_gate", "schedule_run",
            "handoff", "bulk_update", "bulk_delete", "api_key_update",
        ]}

    # ============ Export ============

    @api_router.get("/channels/{channel_id}/export")
    async def export_channel(channel_id: str, request: Request, format: str = "json"):
        """Export all messages from a channel"""
        user = await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        messages = await db.messages.find({"channel_id": channel_id}, {"_id": 0}).sort("created_at", 1).to_list(500)

        await log_audit(db, user["user_id"], "export", "channel", channel_id, {"format": format, "message_count": len(messages)}, channel.get("workspace_id", ""))

        if format == "markdown":
            lines = [f"# Channel: {channel.get('name', channel_id)}\n"]
            for m in messages:
                sender = m.get("sender_name", "Unknown")
                time = m.get("created_at", "")[:19]
                content = m.get("content", "")
                lines.append(f"**{sender}** ({time}):\n{content}\n")
            return JSONResponse({"content": "\n".join(lines), "format": "markdown", "filename": f"{channel.get('name', 'channel')}.md"})

        return {"channel": channel, "messages": messages, "format": "json", "exported_at": datetime.now(timezone.utc).isoformat()}

    @api_router.get("/workspaces/{workspace_id}/export")
    async def export_workspace(workspace_id: str, request: Request):
        """Export entire workspace data"""
        user = await _authed_user(request, workspace_id)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")

        channels = await db.channels.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(50)
        projects = await db.projects.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(50)
        workflows = await db.workflows.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(50)
        artifacts = await db.artifacts.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(100)
        memory = await db.workspace_memory.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(100)

        # Get tasks for all projects
        project_ids = [p["project_id"] for p in projects]
        tasks = await db.project_tasks.find({"project_id": {"$in": project_ids}}, {"_id": 0}).to_list(500) if project_ids else []

        await log_audit(db, user["user_id"], "export", "workspace", workspace_id, {"channels": len(channels), "projects": len(projects)}, workspace_id)

        return {
            "workspace": workspace,
            "channels": channels,
            "projects": projects,
            "tasks": tasks,
            "workflows": workflows,
            "artifacts": artifacts,
            "memory": memory,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    @api_router.get("/workflows/{workflow_id}/export")
    async def export_workflow(workflow_id: str, request: Request):
        """Export a workflow with all nodes, edges, and run history"""
        user = await get_current_user(request)
        workflow = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not workflow:
            raise HTTPException(404, "Workflow not found")
        nodes = await db.workflow_nodes.find({"workflow_id": workflow_id}, {"_id": 0}).to_list(100)
        edges = await db.workflow_edges.find({"workflow_id": workflow_id}, {"_id": 0}).to_list(200)
        runs = await db.workflow_runs.find({"workflow_id": workflow_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)

        await log_audit(db, user["user_id"], "export", "workflow", workflow_id, {"nodes": len(nodes), "runs": len(runs)}, workflow.get("workspace_id", ""))

        return {"workflow": workflow, "nodes": nodes, "edges": edges, "runs": runs, "exported_at": datetime.now(timezone.utc).isoformat()}

    @api_router.get("/workspaces/{workspace_id}/export/csv")
    async def export_workspace_csv(workspace_id: str, request: Request):
        """Export workspace tasks as CSV"""
        user = await _authed_user(request, workspace_id)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")

        projects = await db.projects.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(50)
        pids = [p["project_id"] for p in projects]
        pmap = {p["project_id"]: p["name"] for p in projects}
        tasks = await db.project_tasks.find({"project_id": {"$in": pids}}, {"_id": 0}).to_list(500) if pids else []

        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Task ID", "Title", "Description", "Status", "Priority", "Project", "Assignee", "Created At"])
        for t in tasks:
            writer.writerow([
                t.get("task_id", ""), t.get("title", ""), t.get("description", "")[:200],
                t.get("status", ""), t.get("priority", ""),
                pmap.get(t.get("project_id", ""), ""), t.get("assignee_name", ""),
                t.get("created_at", "")[:19],
            ])

        await log_audit(db, user["user_id"], "export", "workspace", workspace_id, {"format": "csv"}, workspace_id)
        return JSONResponse({"content": output.getvalue(), "format": "csv", "filename": f"{workspace['name']}-tasks.csv"})

    @api_router.get("/channels/{channel_id}/export/csv")
    async def export_channel_csv(channel_id: str, request: Request):
        """Export channel messages as CSV"""
        user = await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        messages = await db.messages.find({"channel_id": channel_id}, {"_id": 0}).sort("created_at", 1).to_list(500)

        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Message ID", "Sender", "Type", "Content", "Created At"])
        for m in messages:
            writer.writerow([
                m.get("message_id", ""), m.get("sender_name", ""),
                m.get("sender_type", ""), m.get("content", "")[:500],
                m.get("created_at", "")[:19],
            ])

        await log_audit(db, user["user_id"], "export", "channel", channel_id, {"format": "csv"}, channel.get("workspace_id", ""))
        return JSONResponse({"content": output.getvalue(), "format": "csv", "filename": f"{channel.get('name', 'channel')}-messages.csv"})

    # Make log_audit available to other modules
    api_router.log_audit = lambda **kw: log_audit(db, **kw)
