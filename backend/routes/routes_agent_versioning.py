"""Agent Versioning & Rollback — Snapshot and restore agent configurations + knowledge.

Creates immutable version snapshots that capture agent config, skills, training state,
and optionally knowledge chunk IDs for point-in-time restore.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)


class CreateVersionRequest(BaseModel):
    label: str = Field("", max_length=100)
    description: str = Field("", max_length=500)
    include_knowledge: bool = True


def register_agent_versioning_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/versions")
    async def create_version(ws_id: str, agent_id: str, data: CreateVersionRequest, request: Request):
        """Create a version snapshot of the agent's current state."""
        user = await _authed_user(request, ws_id)
        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")

        now = datetime.now(timezone.utc).isoformat()
        version_id = f"ver_{uuid.uuid4().hex[:12]}"

        # Count existing versions for numbering
        version_count = await db.agent_versions.count_documents({"agent_id": agent_id})

        # Snapshot knowledge chunk IDs
        knowledge_ids = []
        knowledge_count = 0
        if data.include_knowledge:
            chunks = await db.agent_knowledge.find(
                {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}},
                {"_id": 0, "chunk_id": 1}
            ).to_list(500)
            knowledge_ids = [c["chunk_id"] for c in chunks]
            knowledge_count = len(knowledge_ids)

        version = {
            "version_id": version_id,
            "agent_id": agent_id,
            "workspace_id": ws_id,
            "version_number": version_count + 1,
            "label": data.label or f"v{version_count + 1}",
            "description": data.description,
            "created_by": user["user_id"],
            "snapshot": {
                "name": agent.get("name"),
                "model": agent.get("model"),
                "system_prompt": agent.get("system_prompt"),
                "personality": agent.get("personality"),
                "skills": agent.get("skills") or [],
                "tools": agent.get("tools") or [],
                "guardrails": agent.get("guardrails") or {},
                "training": agent.get("training") or {},
            },
            "knowledge_chunk_ids": knowledge_ids,
            "knowledge_count": knowledge_count,
            "created_at": now,
        }

        await db.agent_versions.insert_one(version)
        version.pop("_id", None)
        return version

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/versions")
    async def list_versions(ws_id: str, agent_id: str, request: Request):
        """List all version snapshots for an agent."""
        user = await _authed_user(request, ws_id)
        versions = await db.agent_versions.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "version_id": 1, "version_number": 1, "label": 1,
             "description": 1, "created_by": 1, "knowledge_count": 1,
             "created_at": 1, "snapshot.name": 1, "snapshot.model": 1}
        ).sort("version_number", -1).limit(50).to_list(50)
        return {"versions": versions, "total": len(versions)}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/versions/{version_id}")
    async def get_version_detail(ws_id: str, agent_id: str, version_id: str, request: Request):
        """Get full version snapshot details."""
        user = await _authed_user(request, ws_id)
        version = await db.agent_versions.find_one(
            {"version_id": version_id, "agent_id": agent_id}, {"_id": 0}
        )
        if not version:
            raise HTTPException(404, "Version not found")
        return version

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/versions/{version_id}/rollback")
    async def rollback_to_version(ws_id: str, agent_id: str, version_id: str, request: Request):
        """Restore an agent to a previous version snapshot."""
        user = await _authed_user(request, ws_id)
        version = await db.agent_versions.find_one(
            {"version_id": version_id, "agent_id": agent_id}, {"_id": 0}
        )
        if not version:
            raise HTTPException(404, "Version not found")

        snapshot = version.get("snapshot") or {}
        now = datetime.now(timezone.utc).isoformat()

        # Auto-snapshot current state before rollback
        current_agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id}, {"_id": 0}
        )
        if current_agent:
            pre_rollback = {
                "version_id": f"ver_{uuid.uuid4().hex[:12]}",
                "agent_id": agent_id,
                "workspace_id": ws_id,
                "version_number": (await db.agent_versions.count_documents({"agent_id": agent_id})) + 1,
                "label": "Pre-rollback auto-snapshot",
                "description": f"Auto-created before rollback to {version.get('label', version_id)}",
                "created_by": user["user_id"],
                "snapshot": {
                    "name": current_agent.get("name"),
                    "model": current_agent.get("model"),
                    "system_prompt": current_agent.get("system_prompt"),
                    "personality": current_agent.get("personality"),
                    "skills": current_agent.get("skills") or [],
                    "tools": current_agent.get("tools") or [],
                    "guardrails": current_agent.get("guardrails") or {},
                    "training": current_agent.get("training") or {},
                },
                "knowledge_chunk_ids": [],
                "knowledge_count": 0,
                "created_at": now,
            }
            await db.agent_versions.insert_one(pre_rollback)

        # Apply version snapshot to agent
        update_fields = {}
        for key in ["name", "model", "system_prompt", "personality", "skills", "tools", "guardrails", "training"]:
            if key in snapshot:
                update_fields[key] = snapshot[key]
        update_fields["updated_at"] = now

        await db.nexus_agents.update_one(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"$set": update_fields}
        )

        # Restore knowledge if version has chunk IDs
        knowledge_restored = 0
        if version.get("knowledge_chunk_ids"):
            # Unflag all chunks from this version
            result = await db.agent_knowledge.update_many(
                {"agent_id": agent_id, "chunk_id": {"$in": version["knowledge_chunk_ids"]}},
                {"$set": {"flagged": False}}
            )
            knowledge_restored = result.modified_count
            # Flag chunks NOT in this version
            await db.agent_knowledge.update_many(
                {"agent_id": agent_id, "chunk_id": {"$nin": version["knowledge_chunk_ids"]}},
                {"$set": {"flagged": True}}
            )

        logger.info(f"Rolled back agent {agent_id} to version {version_id} ({version.get('label')})")
        return {
            "rolled_back_to": version_id,
            "label": version.get("label"),
            "config_restored": list(update_fields.keys()),
            "knowledge_restored": knowledge_restored,
        }

    @api_router.delete("/workspaces/{ws_id}/agents/{agent_id}/versions/{version_id}")
    async def delete_version(ws_id: str, agent_id: str, version_id: str, request: Request):
        """Delete a version snapshot."""
        user = await _authed_user(request, ws_id)
        result = await db.agent_versions.delete_one(
            {"version_id": version_id, "agent_id": agent_id}
        )
        if result.deleted_count == 0:
            raise HTTPException(404, "Version not found")
        return {"deleted": version_id}
