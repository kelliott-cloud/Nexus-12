"""Smart Inbox core routes — threads, triage, actions, search."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from nexus_utils import now_iso
from nexus_config import FEATURE_FLAGS

logger = logging.getLogger(__name__)


class MailActionRequest(BaseModel):
    connection_id: str
    thread_id: str
    action_type: str = Field(..., description="archive, label, move, flag, mark_read, mark_unread, draft_reply, send")
    payload: dict = Field(default_factory=dict)


class TriageRequest(BaseModel):
    thread_ids: List[str] = Field(default_factory=list, description="Empty = triage all unprocessed")
    connection_id: Optional[str] = None


def register_smart_inbox_routes(api_router, db, get_current_user):

    def _check_flag():
        if not FEATURE_FLAGS.get("smart_inbox", {}).get("enabled", False):
            raise HTTPException(501, FEATURE_FLAGS.get("smart_inbox", {}).get("reason", "Smart Inbox not enabled"))

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    # ============ Threads ============

    @api_router.get("/workspaces/{ws_id}/mail/threads")
    async def list_threads(ws_id: str, request: Request, folder: str = "inbox",
                           connection_id: str = "", limit: int = 50, offset: int = 0,
                           priority: str = "", category: str = ""):
        _check_flag()
        await _authed(request, ws_id)
        query = {"workspace_id": ws_id}
        if connection_id:
            query["connection_id"] = connection_id
        if folder:
            query["folder"] = folder
        if priority:
            query["priority"] = priority
        if category:
            query["category"] = category
        total = await db.mail_threads.count_documents(query)
        threads = await db.mail_threads.find(query, {"_id": 0}).sort("last_message_at", -1).skip(offset).limit(limit).to_list(limit)
        return {"threads": threads, "total": total, "offset": offset, "limit": limit}

    @api_router.get("/workspaces/{ws_id}/mail/threads/{thread_id}")
    async def get_thread(ws_id: str, thread_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        thread = await db.mail_threads.find_one(
            {"thread_id": thread_id, "workspace_id": ws_id}, {"_id": 0})
        if not thread:
            raise HTTPException(404, "Thread not found")
        messages = await db.mail_messages.find(
            {"thread_id": thread_id, "workspace_id": ws_id}, {"_id": 0}
        ).sort("received_at", 1).to_list(100)
        return {"thread": thread, "messages": messages}

    @api_router.get("/workspaces/{ws_id}/mail/search")
    async def search_threads(ws_id: str, request: Request, q: str = "", limit: int = 25):
        _check_flag()
        await _authed(request, ws_id)
        if not q.strip():
            return {"threads": [], "total": 0}
        from nexus_utils import safe_regex
        regex = {"$regex": safe_regex(q), "$options": "i"}
        query = {"workspace_id": ws_id, "$or": [
            {"subject": regex}, {"snippet": regex}, {"sender": regex},
        ]}
        total = await db.mail_threads.count_documents(query)
        threads = await db.mail_threads.find(query, {"_id": 0}).sort("last_message_at", -1).limit(limit).to_list(limit)
        return {"threads": threads, "total": total}

    # ============ Triage ============

    @api_router.post("/workspaces/{ws_id}/mail/triage")
    async def triage_threads(ws_id: str, data: TriageRequest, request: Request, bg: BackgroundTasks):
        _check_flag()
        user = await _authed(request, ws_id)
        query = {"workspace_id": ws_id, "triage_status": {"$ne": "processed"}}
        if data.thread_ids:
            query["thread_id"] = {"$in": data.thread_ids}
        if data.connection_id:
            query["connection_id"] = data.connection_id
        threads = await db.mail_threads.find(query, {"_id": 0, "thread_id": 1, "subject": 1, "snippet": 1}).to_list(100)
        if not threads:
            return {"triaged": 0, "message": "No threads to triage"}
        bg.add_task(_run_triage, db, ws_id, threads, user["user_id"])
        return {"triaged": len(threads), "status": "processing"}

    # ============ Actions ============

    @api_router.post("/workspaces/{ws_id}/mail/actions")
    async def create_action(ws_id: str, data: MailActionRequest, request: Request, bg: BackgroundTasks):
        _check_flag()
        user = await _authed(request, ws_id)
        # Check thread exists
        thread = await db.mail_threads.find_one(
            {"thread_id": data.thread_id, "workspace_id": ws_id}, {"_id": 0, "subject": 1})
        if not thread:
            raise HTTPException(404, "Thread not found")
        # Check delegation mode
        conn = await db.mail_connections.find_one(
            {"connection_id": data.connection_id, "workspace_id": ws_id}, {"_id": 0, "delegation_mode": 1})
        delegation = (conn or {}).get("delegation_mode", "recommend")
        action_id = f"mact_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        action = {
            "action_id": action_id, "workspace_id": ws_id,
            "connection_id": data.connection_id, "thread_id": data.thread_id,
            "action_type": data.action_type, "payload": data.payload,
            "status": "pending_review" if delegation in ("observe", "recommend") else "approved",
            "created_by": user["user_id"], "created_at": now,
            "source": "user",
        }
        await db.mail_actions.insert_one(action)
        action.pop("_id", None)
        # Auto-execute if safe-auto or full delegation
        if action["status"] == "approved":
            bg.add_task(_execute_action, db, action_id)
        # Audit
        await _audit_log(db, ws_id, user["user_id"], "action_created", action_id, data.action_type, {"thread": data.thread_id})
        return action

    # ============ Review Queue ============

    @api_router.get("/workspaces/{ws_id}/mail/review")
    async def list_review_queue(ws_id: str, request: Request, limit: int = 50):
        _check_flag()
        await _authed(request, ws_id)
        actions = await db.mail_actions.find(
            {"workspace_id": ws_id, "status": "pending_review"}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"actions": actions, "total": len(actions)}

    @api_router.post("/workspaces/{ws_id}/mail/review/{action_id}/approve")
    async def approve_action(ws_id: str, action_id: str, request: Request, bg: BackgroundTasks):
        _check_flag()
        user = await _authed(request, ws_id)
        result = await db.mail_actions.update_one(
            {"action_id": action_id, "workspace_id": ws_id, "status": "pending_review"},
            {"$set": {"status": "approved", "reviewed_by": user["user_id"], "reviewed_at": now_iso()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Action not found or already reviewed")
        bg.add_task(_execute_action, db, action_id)
        await _audit_log(db, ws_id, user["user_id"], "action_approved", action_id)
        return {"status": "approved"}

    @api_router.post("/workspaces/{ws_id}/mail/review/{action_id}/dismiss")
    async def dismiss_action(ws_id: str, action_id: str, request: Request):
        _check_flag()
        user = await _authed(request, ws_id)
        result = await db.mail_actions.update_one(
            {"action_id": action_id, "workspace_id": ws_id, "status": "pending_review"},
            {"$set": {"status": "dismissed", "reviewed_by": user["user_id"], "reviewed_at": now_iso()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Action not found or already reviewed")
        await _audit_log(db, ws_id, user["user_id"], "action_dismissed", action_id)
        return {"status": "dismissed"}

    # ============ Stats ============

    @api_router.get("/workspaces/{ws_id}/mail/stats")
    async def mail_stats(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        connections = await db.mail_connections.count_documents({"workspace_id": ws_id, "status": "active"})
        threads = await db.mail_threads.count_documents({"workspace_id": ws_id})
        unread = await db.mail_threads.count_documents({"workspace_id": ws_id, "is_read": False})
        pending_review = await db.mail_actions.count_documents({"workspace_id": ws_id, "status": "pending_review"})
        return {
            "connections": connections, "threads": threads,
            "unread": unread, "pending_review": pending_review,
        }

    # ============ Phase 2: Safe Autonomous + Drafts ============

    @api_router.post("/workspaces/{ws_id}/mail/auto-process")
    async def auto_process_threads(ws_id: str, request: Request, bg: BackgroundTasks):
        """Auto-process threads using safe_auto delegation mode — archive, label, move, flag, mark_read only."""
        _check_flag()
        user = await _authed(request, ws_id)
        body = await request.json()
        connection_id = body.get("connection_id", "")
        conn = await db.mail_connections.find_one(
            {"connection_id": connection_id, "workspace_id": ws_id}, {"_id": 0, "delegation_mode": 1})
        if not conn:
            raise HTTPException(404, "Connection not found")
        if conn.get("delegation_mode") not in ("safe_auto", "full"):
            raise HTTPException(400, f"Connection delegation mode is '{conn.get('delegation_mode')}' — safe_auto or full required for auto-processing")
        SAFE_ACTIONS = {"archive", "label", "move", "flag", "mark_read", "mark_unread"}
        rules = await db.mail_rules.find(
            {"workspace_id": ws_id, "enabled": True, "$or": [{"connection_id": connection_id}, {"connection_id": None}]},
            {"_id": 0}
        ).to_list(100)
        threads = await db.mail_threads.find(
            {"workspace_id": ws_id, "connection_id": connection_id, "triage_status": "processed", "auto_processed": {"$ne": True}},
            {"_id": 0, "thread_id": 1, "subject": 1, "sender": 1, "labels": 1, "folder": 1}
        ).limit(100).to_list(100)
        queued = 0
        for thread in threads:
            for rule in rules:
                if _rule_matches(thread, rule):
                    for action_def in rule.get("actions", []):
                        if action_def.get("action_type") in SAFE_ACTIONS:
                            action_id = f"mact_{uuid.uuid4().hex[:12]}"
                            await db.mail_actions.insert_one({
                                "action_id": action_id, "workspace_id": ws_id,
                                "connection_id": connection_id, "thread_id": thread["thread_id"],
                                "action_type": action_def["action_type"], "payload": action_def.get("payload", {}),
                                "status": "approved", "source": "auto_rule", "rule_id": rule.get("rule_id"),
                                "created_by": "system", "created_at": now_iso(),
                            })
                            bg.add_task(_execute_action, db, action_id)
                            queued += 1
                            await db.mail_rules.update_one({"rule_id": rule["rule_id"]}, {"$inc": {"execution_count": 1}})
            await db.mail_threads.update_one({"thread_id": thread["thread_id"]}, {"$set": {"auto_processed": True}})
        return {"processed_threads": len(threads), "actions_queued": queued}

    @api_router.post("/workspaces/{ws_id}/mail/drafts")
    async def create_draft(ws_id: str, request: Request):
        """Create a draft reply to a thread (Phase 2)."""
        _check_flag()
        user = await _authed(request, ws_id)
        body = await request.json()
        thread_id = body.get("thread_id", "")
        connection_id = body.get("connection_id", "")
        body_text = body.get("body", "")
        subject = body.get("subject", "")
        if not thread_id or not body_text:
            raise HTTPException(400, "thread_id and body required")
        draft_id = f"mdraft_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        draft = {
            "draft_id": draft_id, "workspace_id": ws_id, "connection_id": connection_id,
            "thread_id": thread_id, "subject": subject, "body": body_text,
            "status": "draft", "created_by": user["user_id"], "created_at": now,
        }
        await db.mail_drafts.insert_one(draft)
        draft.pop("_id", None)
        await _audit_log(db, ws_id, user["user_id"], "draft_created", draft_id, "draft", {"thread_id": thread_id})
        return draft

    @api_router.get("/workspaces/{ws_id}/mail/drafts")
    async def list_drafts(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        drafts = await db.mail_drafts.find(
            {"workspace_id": ws_id, "status": "draft"}, {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        return {"drafts": drafts}

    @api_router.post("/workspaces/{ws_id}/mail/drafts/{draft_id}/send")
    async def send_draft(ws_id: str, draft_id: str, request: Request):
        """Send a draft (Phase 2 — marks as sent, actual delivery requires provider integration)."""
        _check_flag()
        user = await _authed(request, ws_id)
        result = await db.mail_drafts.update_one(
            {"draft_id": draft_id, "workspace_id": ws_id, "status": "draft"},
            {"$set": {"status": "sent", "sent_by": user["user_id"], "sent_at": now_iso()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Draft not found or already sent")
        await _audit_log(db, ws_id, user["user_id"], "draft_sent", draft_id, "send")
        return {"status": "sent"}

    @api_router.delete("/workspaces/{ws_id}/mail/drafts/{draft_id}")
    async def delete_draft(ws_id: str, draft_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        await db.mail_drafts.delete_one({"draft_id": draft_id, "workspace_id": ws_id})
        return {"status": "deleted"}

    # ============ Phase 2: Webhook Events ============

    @api_router.post("/workspaces/{ws_id}/mail/webhook-test")
    async def test_mail_webhook(ws_id: str, request: Request):
        """Fire a test webhook event for mail integration testing."""
        _check_flag()
        user = await _authed(request, ws_id)
        try:
            from routes.routes_webhooks import emit_webhook_event
            await emit_webhook_event(db, ws_id, "mail.test", {
                "workspace_id": ws_id, "triggered_by": user["user_id"], "timestamp": now_iso(),
            })
            return {"status": "webhook_sent"}
        except Exception as e:
            return {"status": "webhook_failed", "error": str(e)[:200]}

    # ============ Phase 3: Full Delegation + Rollback ============

    @api_router.post("/workspaces/{ws_id}/mail/delegate")
    async def delegate_action(ws_id: str, request: Request, bg: BackgroundTasks):
        """Full delegation: execute send, delete, or other destructive actions (Phase 3)."""
        _check_flag()
        user = await _authed(request, ws_id)
        body = await request.json()
        connection_id = body.get("connection_id", "")
        conn = await db.mail_connections.find_one(
            {"connection_id": connection_id, "workspace_id": ws_id}, {"_id": 0, "delegation_mode": 1})
        if not conn or conn.get("delegation_mode") != "full":
            raise HTTPException(403, "Full delegation mode required for this action")
        action_type = body.get("action_type", "")
        thread_id = body.get("thread_id", "")
        if action_type not in ("send", "delete", "forward", "move_folder"):
            raise HTTPException(400, f"Invalid delegated action: {action_type}")
        action_id = f"mact_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        action = {
            "action_id": action_id, "workspace_id": ws_id, "connection_id": connection_id,
            "thread_id": thread_id, "action_type": action_type,
            "payload": body.get("payload", {}), "status": "approved",
            "source": "delegation", "created_by": user["user_id"], "created_at": now,
            "rollback_data": body.get("rollback_data"),
        }
        await db.mail_actions.insert_one(action)
        action.pop("_id", None)
        bg.add_task(_execute_action, db, action_id)
        await _audit_log(db, ws_id, user["user_id"], "delegated_action", action_id, action_type, {"thread_id": thread_id})
        return action

    @api_router.post("/workspaces/{ws_id}/mail/actions/{action_id}/rollback")
    async def rollback_action(ws_id: str, action_id: str, request: Request):
        """Rollback a previously executed action (Phase 3)."""
        _check_flag()
        user = await _authed(request, ws_id)
        action = await db.mail_actions.find_one(
            {"action_id": action_id, "workspace_id": ws_id, "status": "executed"}, {"_id": 0})
        if not action:
            raise HTTPException(404, "Action not found or not executed")
        if not action.get("rollback_data"):
            raise HTTPException(400, "Action has no rollback data — cannot undo")
        rollback_id = f"mact_{uuid.uuid4().hex[:12]}"
        await db.mail_actions.insert_one({
            "action_id": rollback_id, "workspace_id": ws_id,
            "connection_id": action.get("connection_id"),
            "thread_id": action.get("thread_id"),
            "action_type": f"rollback_{action['action_type']}",
            "payload": action["rollback_data"], "status": "executed",
            "source": "rollback", "rollback_of": action_id,
            "created_by": user["user_id"], "created_at": now_iso(),
        })
        await db.mail_actions.update_one(
            {"action_id": action_id}, {"$set": {"status": "rolled_back", "rolled_back_at": now_iso()}})
        await _audit_log(db, ws_id, user["user_id"], "action_rolled_back", action_id, "rollback", {"rollback_id": rollback_id})
        return {"status": "rolled_back", "rollback_id": rollback_id}

    @api_router.get("/workspaces/{ws_id}/mail/digest")
    async def get_daily_digest(ws_id: str, request: Request):
        """Get daily email digest summary (Phase 3)."""
        _check_flag()
        await _authed(request, ws_id)
        from datetime import timedelta
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        new_threads = await db.mail_threads.count_documents({"workspace_id": ws_id, "last_message_at": {"$gte": yesterday}})
        actions_taken = await db.mail_actions.count_documents({"workspace_id": ws_id, "created_at": {"$gte": yesterday}, "status": "executed"})
        high_priority = await db.mail_threads.count_documents({"workspace_id": ws_id, "priority": "high", "is_read": False})
        return {"new_threads": new_threads, "actions_taken": actions_taken, "high_priority_unread": high_priority, "period": "24h"}



def _rule_matches(thread: dict, rule: dict) -> bool:
    """Check if a mail thread matches a rule's conditions."""
    import re
    conditions = rule.get("conditions", [])
    match_mode = rule.get("match_mode", "all")
    if not conditions:
        return False
    results = []
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("operator", "contains")
        value = cond.get("value", "").lower()
        thread_val = str(thread.get(field, "")).lower()
        if op == "contains":
            results.append(value in thread_val)
        elif op == "equals":
            results.append(thread_val == value)
        elif op == "starts_with":
            results.append(thread_val.startswith(value))
        elif op == "ends_with":
            results.append(thread_val.endswith(value))
        elif op == "not_contains":
            results.append(value not in thread_val)
        elif op == "regex":
            try:
                results.append(bool(re.search(value, thread_val)))
            except re.error:
                results.append(False)
        else:
            results.append(False)
    return all(results) if match_mode == "all" else any(results)


async def _run_triage(db, ws_id, threads, user_id):
    """Background: AI triage — score priority and categorize threads."""
    for t in threads:
        try:
            # Phase 1: simple rule-based triage
            subject = (t.get("subject") or "").lower()
            priority = "normal"
            category = "general"
            if any(w in subject for w in ["urgent", "asap", "critical", "action required"]):
                priority = "high"
            elif any(w in subject for w in ["newsletter", "digest", "weekly", "unsubscribe"]):
                priority = "low"
                category = "newsletter"
            elif any(w in subject for w in ["invoice", "payment", "receipt", "order"]):
                category = "transactional"
            elif any(w in subject for w in ["meeting", "calendar", "invite", "rsvp"]):
                category = "calendar"

            await db.mail_threads.update_one(
                {"thread_id": t["thread_id"], "workspace_id": ws_id},
                {"$set": {"priority": priority, "category": category,
                          "triage_status": "processed", "triaged_at": now_iso()}})
        except Exception as e:
            logger.warning(f"Triage failed for thread {t.get('thread_id')}: {e}")


async def _execute_action(db, action_id):
    """Background: execute an approved mail action."""
    action = await db.mail_actions.find_one({"action_id": action_id}, {"_id": 0})
    if not action or action.get("status") not in ("approved",):
        return
    try:
        # Phase 1: mark as executed (actual provider execution in Phase 2/3)
        await db.mail_actions.update_one(
            {"action_id": action_id},
            {"$set": {"status": "executed", "executed_at": now_iso()}})
        logger.info(f"Action {action_id} ({action.get('action_type')}) executed")
    except Exception as e:
        logger.error(f"Action {action_id} failed: {e}")
        await db.mail_actions.update_one(
            {"action_id": action_id},
            {"$set": {"status": "failed", "error": str(e)[:500]}})


async def _audit_log(db, ws_id, user_id, event_type, resource_id, action_type=None, details=None):
    await db.mail_audit_log.insert_one({
        "audit_id": f"maud_{uuid.uuid4().hex[:12]}",
        "workspace_id": ws_id, "user_id": user_id,
        "event_type": event_type, "resource_id": resource_id,
        "action_type": action_type, "details": details or {},
        "timestamp": now_iso(),
    })
