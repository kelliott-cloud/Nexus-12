"""Deduplication Engine — Prevents agents from creating duplicate records.

Before any project, task, milestone, artifact, or repo file is created,
the engine checks for existing duplicates using name similarity and content hashing.
If a duplicate is found, creation is blocked and the agent must provide justification.
Overrides are documented in the `duplicate_overrides` collection.
"""
import hashlib
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Similarity threshold (0.0 to 1.0) — above this is considered a duplicate
SIMILARITY_THRESHOLD = 0.8


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0-1)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def content_hash(content: str) -> str:
    """SHA-256 hash of content for exact duplicate detection."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


async def check_duplicate_project(db, workspace_id: str, name: str, description: str = ""):
    """Check if a project with a similar name already exists in the workspace."""
    existing = await db.projects.find(
        {"workspace_id": workspace_id, "status": {"$ne": "archived"}},
        {"_id": 0, "project_id": 1, "name": 1, "description": 1}
    ).to_list(100)

    for proj in existing:
        name_sim = similarity(name, proj.get("name", ""))
        if name_sim >= SIMILARITY_THRESHOLD:
            return {
                "is_duplicate": True,
                "match_type": "name",
                "similarity": round(name_sim, 2),
                "existing_id": proj["project_id"],
                "existing_name": proj["name"],
                "entity_type": "project",
            }
    return {"is_duplicate": False}


async def check_duplicate_task(db, project_id: str, title: str, description: str = ""):
    """Check if a task with a similar title exists in the same project."""
    existing = await db.project_tasks.find(
        {"project_id": project_id, "status": {"$ne": "done"}},
        {"_id": 0, "task_id": 1, "title": 1, "description": 1}
    ).to_list(200)

    for task in existing:
        title_sim = similarity(title, task.get("title", ""))
        if title_sim >= SIMILARITY_THRESHOLD:
            return {
                "is_duplicate": True,
                "match_type": "title",
                "similarity": round(title_sim, 2),
                "existing_id": task["task_id"],
                "existing_name": task["title"],
                "entity_type": "task",
            }
    return {"is_duplicate": False}


async def check_duplicate_milestone(db, project_id: str, name: str):
    """Check if a milestone with a similar name exists in the same project."""
    existing = await db.milestones.find(
        {"project_id": project_id},
        {"_id": 0, "milestone_id": 1, "name": 1}
    ).to_list(50)

    for ms in existing:
        name_sim = similarity(name, ms.get("name", ""))
        if name_sim >= SIMILARITY_THRESHOLD:
            return {
                "is_duplicate": True,
                "match_type": "name",
                "similarity": round(name_sim, 2),
                "existing_id": ms["milestone_id"],
                "existing_name": ms["name"],
                "entity_type": "milestone",
            }
    return {"is_duplicate": False}


async def check_duplicate_artifact(db, workspace_id: str, name: str, content: str = ""):
    """Check for duplicate artifacts by name or content hash."""
    # Check by name
    existing = await db.artifacts.find(
        {"workspace_id": workspace_id},
        {"_id": 0, "artifact_id": 1, "name": 1, "content": 1}
    ).to_list(200)

    c_hash = content_hash(content) if content else ""

    for art in existing:
        name_sim = similarity(name, art.get("name", ""))
        if name_sim >= SIMILARITY_THRESHOLD:
            return {
                "is_duplicate": True,
                "match_type": "name",
                "similarity": round(name_sim, 2),
                "existing_id": art["artifact_id"],
                "existing_name": art["name"],
                "entity_type": "artifact",
            }
        # Content hash match
        if c_hash and content_hash(art.get("content", "")) == c_hash:
            return {
                "is_duplicate": True,
                "match_type": "content_hash",
                "similarity": 1.0,
                "existing_id": art["artifact_id"],
                "existing_name": art["name"],
                "entity_type": "artifact",
            }
    return {"is_duplicate": False}


async def check_duplicate_repo_file(db, workspace_id: str, path: str, content: str = ""):
    """Check for duplicate repo files by content hash across the workspace."""
    if not content:
        return {"is_duplicate": False}

    c_hash = content_hash(content)
    existing = await db.repo_files.find(
        {"workspace_id": workspace_id, "is_deleted": {"$ne": True}},
        {"_id": 0, "file_id": 1, "path": 1, "content": 1}
    ).to_list(500)

    for f in existing:
        if f.get("path") == path:
            continue  # Same file being updated — not a duplicate
        if content_hash(f.get("content", "")) == c_hash:
            return {
                "is_duplicate": True,
                "match_type": "content_hash",
                "similarity": 1.0,
                "existing_id": f["file_id"],
                "existing_name": f["path"],
                "entity_type": "repo_file",
            }
    return {"is_duplicate": False}


async def log_duplicate_override(db, workspace_id: str, channel_id: str, agent_name: str,
                                  entity_type: str, entity_name: str, existing_id: str,
                                  existing_name: str, justification: str, similarity_score: float):
    """Log when an agent overrides a duplicate check with justification."""
    import uuid
    override = {
        "override_id": f"dup_{uuid.uuid4().hex[:12]}",
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "agent_name": agent_name,
        "entity_type": entity_type,
        "entity_name": entity_name,
        "existing_id": existing_id,
        "existing_name": existing_name,
        "justification": justification[:500],
        "similarity_score": similarity_score,
        "status": "overridden",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.duplicate_overrides.insert_one(override)
    logger.info(f"Duplicate override: {agent_name} created {entity_type} '{entity_name}' despite existing '{existing_name}' — reason: {justification[:100]}")
    return override["override_id"]


def build_duplicate_block_message(dup_result: dict, tool_name: str) -> str:
    """Build the error message returned to the agent when a duplicate is detected."""
    return (
        f"DUPLICATE BLOCKED: A {dup_result['entity_type']} named \"{dup_result['existing_name']}\" "
        f"already exists (ID: {dup_result['existing_id']}, similarity: {dup_result['similarity']:.0%}). "
        f"To override, call {tool_name} again with an additional 'override_reason' parameter "
        f"explaining why this is NOT a duplicate or why a separate record is needed."
    )


DEDUP_PROMPT_INJECTION = """
=== DEDUPLICATION RULES ===
Before creating ANY project, task, milestone, or artifact, you MUST consider:
1. Does something with this name or purpose already exist?
2. If the system blocks your creation as a duplicate, you MUST either:
   a. Use the existing item instead (preferred), OR
   b. Provide a clear 'override_reason' parameter explaining why a new record is justified
3. Never create duplicate records without justification — the system will block you.
4. When blocked, reference the existing item by its ID and explain why yours is different.
=== END DEDUPLICATION RULES ===
"""
