"""Helper Action Control — proposal, approval, execution, audit for Nexus Helper actions."""
import uuid
import logging
from datetime import datetime, timezone
from nexus_utils import now_iso

logger = logging.getLogger("helper_actions")

RISK_LEVELS = {
    "read": {"label": "Read Only", "requires_approval": False},
    "write": {"label": "Write", "requires_approval": True},
    "destructive": {"label": "Destructive", "requires_approval": True, "confirm": True},
}

TOOL_PERMISSION_MAP = {
    "create_project": "create_tasks",
    "create_task": "create_tasks",
    "create_milestone": "create_tasks",
    "repo_write_file": "manage_code",
    "repo_delete_file": "manage_code",
    "repo_create_file": "manage_code",
    "wiki_create_page": "manage_docs",
    "wiki_update_page": "manage_docs",
    "memory_add": "manage_knowledge",
    "memory_delete": "manage_knowledge",
    "execute_code": "execute_code",
    "create_artifact": "manage_artifacts",
    "search_messages": None,
    "list_channels": None,
    "list_projects": None,
    "repo_list_files": None,
    "repo_read_file": None,
    "wiki_list_pages": None,
    "wiki_read_page": None,
    "memory_search": None,
}


def classify_risk(tool_calls: list) -> str:
    """Classify risk level based on tool calls."""
    has_destructive = any("delete" in (tc.get("tool") or "").lower() for tc in tool_calls)
    has_write = any(tc.get("tool") in (
        "create_project", "create_task", "create_milestone", "repo_write_file",
        "repo_create_file", "wiki_create_page", "wiki_update_page",
        "memory_add", "execute_code", "create_artifact"
    ) for tc in tool_calls)
    if has_destructive:
        return "destructive"
    if has_write:
        return "write"
    return "read"


def resolve_permissions(tool_calls: list) -> list:
    """Get required workspace permissions for the action."""
    perms = set()
    for tc in tool_calls:
        perm = TOOL_PERMISSION_MAP.get(tc.get("tool"))
        if perm:
            perms.add(perm)
    return sorted(perms)


def validate_tool_calls(tool_calls: list) -> list:
    """Validate tool calls are well-formed. Returns list of errors."""
    errors = []
    if len(tool_calls) > 5:
        errors.append("Maximum 5 tool calls per action")
    for i, tc in enumerate(tool_calls):
        if not tc.get("tool"):
            errors.append(f"Tool call {i}: missing 'tool' field")
        if not isinstance(tc.get("params", {}), dict):
            errors.append(f"Tool call {i}: 'params' must be a dict")
    return errors


async def build_helper_action(db, user_id: str, workspace_id: str, action_data: dict) -> dict:
    """Create a helper action proposal from AI output."""
    action_id = f"hact_{uuid.uuid4().hex[:12]}"
    tool_calls = action_data.get("tool_calls", [])
    risk = classify_risk(tool_calls)
    perms = resolve_permissions(tool_calls)
    requires_approval = RISK_LEVELS.get(risk, {}).get("requires_approval", True)

    action = {
        "action_id": action_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "title": action_data.get("title", "Helper Action"),
        "summary": action_data.get("summary", ""),
        "risk_level": risk,
        "scope": action_data.get("scope", "native"),
        "tool_calls": tool_calls,
        "required_permissions": perms,
        "requires_bridge": action_data.get("scope") == "bridge",
        "status": "auto_approved" if not requires_approval else "pending_review",
        "preview": action_data.get("preview", {}),
        "idempotency_key": action_data.get("idempotency_key") or f"idem_{uuid.uuid4().hex[:8]}",
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.helper_actions.insert_one(action)
    action.pop("_id", None)
    return action


async def execute_helper_action(db, action_id: str, user: dict, workspace_id: str) -> dict:
    """Execute an approved helper action."""
    action = await db.helper_actions.find_one({"action_id": action_id}, {"_id": 0})
    if not action:
        return {"error": "Action not found"}
    if action["status"] not in ("pending_review", "auto_approved", "approved"):
        return {"error": f"Action is {action['status']}, cannot execute"}

    # Idempotency check
    existing = await db.helper_actions.find_one({
        "idempotency_key": action["idempotency_key"],
        "status": "completed",
        "action_id": {"$ne": action_id},
    })
    if existing:
        return {"error": "Duplicate action already completed", "duplicate_of": existing["action_id"]}

    await db.helper_actions.update_one(
        {"action_id": action_id},
        {"$set": {"status": "running", "updated_at": now_iso()}})

    # Phase 3: Detect bundled actions (multiple steps with rollback)
    tool_calls = action.get("tool_calls", [])
    has_rollback = any(tc.get("rollback_tool") for tc in tool_calls)
    if len(tool_calls) > 1 and has_rollback:
        return await execute_bundled_action(db, action_id, user, workspace_id)

    results = []
    try:
        for tc in action.get("tool_calls", []):
            tool_name = tc.get("tool", "")
            params = tc.get("params", {})

            if action.get("scope") == "bridge":
                result = await execute_bridge_tool_call(db, tool_name, params, user, workspace_id)
            else:
                result = await execute_native_tool_call(db, tool_name, params, user, workspace_id)
            results.append({"tool": tool_name, "result": result})

        await db.helper_actions.update_one(
            {"action_id": action_id},
            {"$set": {
                "status": "completed",
                "result": {"summary": f"Executed {len(results)} tool call(s)", "tool_results": results},
                "updated_at": now_iso(),
            }})

        await audit_helper_action(db, action_id, user["user_id"], workspace_id, "executed")
        return {"status": "completed", "result": {"summary": f"Executed {len(results)} tool call(s)", "tool_results": results}}

    except Exception as e:
        logger.error(f"Helper action {action_id} failed: {e}")
        await db.helper_actions.update_one(
            {"action_id": action_id},
            {"$set": {"status": "failed", "error": str(e)[:500], "updated_at": now_iso()}})
        await audit_helper_action(db, action_id, user["user_id"], workspace_id, "failed", {"error": str(e)[:200]})
        return {"status": "failed", "error": str(e)[:500]}


async def execute_native_tool_call(db, tool_name: str, params: dict, user: dict, workspace_id: str) -> dict:
    """Execute a native Nexus tool call."""
    try:
        from routes.routes_ai_tools import execute_tool
        result = await execute_tool(db, workspace_id, tool_name, params, user["user_id"], "helper")
        return {"success": True, "output": str(result)[:1000]}
    except Exception as e:
        return {"success": False, "error": str(e)[:500]}


async def execute_bridge_tool_call(db, tool_name: str, params: dict, user: dict, workspace_id: str) -> dict:
    """Execute a bridge tool call via desktop MCP bridge (Phase 2)."""
    try:
        # Check if bridge is connected for this workspace
        bridge = await db.mcp_connections.find_one(
            {"workspace_id": workspace_id, "status": "connected"}, {"_id": 0, "session_id": 1})
        if not bridge:
            return {"success": False, "error": "Desktop bridge not connected. Open Nexus Desktop to enable bridge actions."}

        # Check tool allowlist
        try:
            from mcp_bridge.tools import get_tool_metadata
            meta = get_tool_metadata(tool_name)
            if meta and meta.get("requires_approval"):
                return {"success": False, "error": f"Bridge tool '{tool_name}' requires additional approval via bridge UI"}
        except ImportError:
            pass

        # Execute via bridge
        try:
            from mcp_bridge.routes import execute_bridge_tool
            result = await execute_bridge_tool(db, bridge["session_id"], tool_name, params, user["user_id"])
            return {"success": True, "output": str(result)[:1000]}
        except Exception as e:
            return {"success": False, "error": f"Bridge execution failed: {str(e)[:300]}"}
    except Exception as e:
        return {"success": False, "error": f"Bridge unavailable: {str(e)[:200]}"}


async def execute_bundled_action(db, action_id: str, user: dict, workspace_id: str) -> dict:
    """Execute a bundled multi-step action (Phase 3) — ordered sequence of tool calls with rollback."""
    action = await db.helper_actions.find_one({"action_id": action_id}, {"_id": 0})
    if not action:
        return {"error": "Action not found"}

    tool_calls = action.get("tool_calls", [])
    if len(tool_calls) > 5:
        return {"error": "Maximum 5 steps per bundled action"}

    await db.helper_actions.update_one(
        {"action_id": action_id},
        {"$set": {"status": "running", "updated_at": now_iso()}})

    completed_steps = []
    rollback_stack = []

    try:
        for i, tc in enumerate(tool_calls):
            tool_name = tc.get("tool", "")
            params = tc.get("params", {})
            step_scope = tc.get("scope", action.get("scope", "native"))

            # Execute step
            if step_scope == "bridge":
                result = await execute_bridge_tool_call(db, tool_name, params, user, workspace_id)
            else:
                result = await execute_native_tool_call(db, tool_name, params, user, workspace_id)

            step_record = {"step": i, "tool": tool_name, "result": result}
            completed_steps.append(step_record)

            # Track rollback data if available
            if tc.get("rollback_tool"):
                rollback_stack.append({
                    "tool": tc["rollback_tool"],
                    "params": tc.get("rollback_params", {}),
                    "scope": step_scope,
                })

            if not result.get("success"):
                # Step failed — rollback completed steps
                rollback_results = []
                for rb in reversed(rollback_stack[:-1]):  # Don't rollback the failed step
                    try:
                        if rb["scope"] == "bridge":
                            rb_result = await execute_bridge_tool_call(db, rb["tool"], rb["params"], user, workspace_id)
                        else:
                            rb_result = await execute_native_tool_call(db, rb["tool"], rb["params"], user, workspace_id)
                        rollback_results.append({"tool": rb["tool"], "result": rb_result})
                    except Exception:
                        pass

                await db.helper_actions.update_one(
                    {"action_id": action_id},
                    {"$set": {
                        "status": "partially_failed",
                        "result": {"completed_steps": completed_steps, "failed_at_step": i, "rollback_results": rollback_results},
                        "error": f"Step {i} ({tool_name}) failed: {result.get('error', 'unknown')}",
                        "updated_at": now_iso(),
                    }})
                await audit_helper_action(db, action_id, user["user_id"], workspace_id, "partially_failed",
                    {"failed_step": i, "rolled_back": len(rollback_results)})
                return {
                    "status": "partially_failed",
                    "completed_steps": len(completed_steps) - 1,
                    "failed_at_step": i,
                    "error": result.get("error"),
                }

            # Update progress
            await db.helper_actions.update_one(
                {"action_id": action_id},
                {"$set": {"progress": int((i + 1) / len(tool_calls) * 100)}})

        # All steps completed
        await db.helper_actions.update_one(
            {"action_id": action_id},
            {"$set": {
                "status": "completed", "progress": 100,
                "result": {"summary": f"All {len(tool_calls)} steps completed", "steps": completed_steps},
                "updated_at": now_iso(),
            }})
        await audit_helper_action(db, action_id, user["user_id"], workspace_id, "bundle_completed",
            {"steps": len(tool_calls)})
        return {"status": "completed", "steps_completed": len(tool_calls), "result": {"steps": completed_steps}}

    except Exception as e:
        logger.error(f"Bundled action {action_id} failed: {e}")
        await db.helper_actions.update_one(
            {"action_id": action_id},
            {"$set": {"status": "failed", "error": str(e)[:500], "updated_at": now_iso()}})
        return {"status": "failed", "error": str(e)[:500]}


async def audit_helper_action(db, action_id: str, user_id: str, workspace_id: str, event: str, details: dict = None):
    """Log helper action events for audit trail."""
    await db.audit_log.insert_one({
        "audit_id": f"haud_{uuid.uuid4().hex[:12]}",
        "event_type": f"helper_action_{event}",
        "resource_type": "helper_action",
        "resource_id": action_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "details": details or {},
        "timestamp": now_iso(),
    })
