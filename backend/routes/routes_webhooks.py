"""Webhooks — outbound webhook registration, event emission, delivery tracking"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
import httpx

logger = logging.getLogger(__name__)

VALID_EVENTS = [
    "message.created", "collaboration.started", "collaboration.completed",
    "task.created", "task.updated", "task.completed",
    "workflow.run.started", "workflow.run.completed", "workflow.run.failed",
    "handoff.created", "schedule.executed",
    "artifact.created", "artifact.updated",
    "member.joined", "member.removed",
    "cost.alert.triggered",
]


class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=10)
    events: List[str]
    name: str = ""
    secret: str = ""
    retry_policy: dict = {"max_retries": 3}


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None


def register_webhook_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import validate_external_url, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.get("/workspaces/{workspace_id}/webhooks")
    async def list_webhooks(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        hooks = await db.webhooks.find({"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return hooks

    @api_router.post("/workspaces/{workspace_id}/webhooks")
    async def create_webhook(workspace_id: str, data: WebhookCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        # W3: SSRF protection — validate webhook URL
        from operator_engine import is_url_safe
        safe, reason = is_url_safe(data.url)
        if not safe:
            raise HTTPException(400, f"Blocked URL: {reason}")
        invalid = [e for e in data.events if e not in VALID_EVENTS]
        if invalid:
            raise HTTPException(400, f"Invalid events: {', '.join(invalid)}")

        hook_id = f"whk_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        hook = {
            "webhook_id": hook_id,
            "workspace_id": workspace_id,
            "url": data.url,
            "events": data.events,
            "name": data.name or data.url[:40],
            "secret": data.secret,
            "enabled": True,
            "failure_count": 0,
            "retry_policy": data.retry_policy,
            "last_triggered_at": None,
            "last_status": None,
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.webhooks.insert_one(hook)
        return {k: v for k, v in hook.items() if k != "_id"}

    @api_router.put("/webhooks/{webhook_id}")
    async def update_webhook(webhook_id: str, data: WebhookUpdate, request: Request):
        user = await get_current_user(request)
        hook = await db.webhooks.find_one({"webhook_id": webhook_id}, {"workspace_id": 1})
        if not hook: raise HTTPException(404, "Webhook not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, hook["workspace_id"])
        updates = {}
        if data.url is not None:
            from operator_engine import is_url_safe
            safe, reason = is_url_safe(data.url)
            if not safe:
                raise HTTPException(400, f"Blocked URL: {reason}")
            updates["url"] = data.url
        if data.events is not None:
            invalid = [e for e in data.events if e not in VALID_EVENTS]
            if invalid:
                raise HTTPException(400, f"Invalid events: {', '.join(invalid)}")
            updates["events"] = data.events
        if data.name is not None:
            updates["name"] = data.name
        if data.enabled is not None:
            updates["enabled"] = data.enabled
            if data.enabled:
                updates["failure_count"] = 0
        if updates:
            await db.webhooks.update_one({"webhook_id": webhook_id}, {"$set": updates})
        return await db.webhooks.find_one({"webhook_id": webhook_id}, {"_id": 0})

    @api_router.delete("/webhooks/{webhook_id}")
    async def delete_webhook(webhook_id: str, request: Request):
        user = await get_current_user(request)
        hook = await db.webhooks.find_one({"webhook_id": webhook_id}, {"workspace_id": 1})
        if not hook: raise HTTPException(404, "Webhook not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, hook["workspace_id"])
        await db.webhooks.delete_one({"webhook_id": webhook_id})
        return {"message": "Webhook deleted"}

    @api_router.post("/webhooks/{webhook_id}/test")
    async def test_webhook(webhook_id: str, request: Request):
        await get_current_user(request)
        hook = await db.webhooks.find_one({"webhook_id": webhook_id}, {"_id": 0})
        if not hook:
            raise HTTPException(404, "Webhook not found")
        payload = {"event": "webhook.test", "webhook_id": webhook_id, "timestamp": datetime.now(timezone.utc).isoformat(), "data": {"message": "Test delivery from Nexus"}}
        result = await _deliver_webhook(hook, payload)
        return result

    @api_router.get("/webhooks/{webhook_id}/deliveries")
    async def get_deliveries(webhook_id: str, request: Request):
        await get_current_user(request)
        deliveries = await db.webhook_deliveries.find({"webhook_id": webhook_id}, {"_id": 0}).sort("timestamp", -1).to_list(20)
        return deliveries

    @api_router.get("/webhooks/events")
    async def get_webhook_events(request: Request):
        await get_current_user(request)
        return {"events": VALID_EVENTS}

    # ============ Dead-Letter Queue ============

    @api_router.get("/workspaces/{workspace_id}/webhooks/dead-letters")
    async def list_dead_letters(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        letters = await db.webhook_dead_letters.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        return {"dead_letters": letters}

    @api_router.post("/webhooks/dead-letters/{dead_letter_id}/retry")
    async def retry_dead_letter(dead_letter_id: str, request: Request):
        await get_current_user(request)
        dl = await db.webhook_dead_letters.find_one({"dead_letter_id": dead_letter_id}, {"_id": 0})
        if not dl:
            raise HTTPException(404, "Dead letter not found")
        hook = await db.webhooks.find_one({"webhook_id": dl["webhook_id"]}, {"_id": 0})
        if not hook:
            raise HTTPException(404, "Webhook no longer exists")
        # Re-enable webhook and retry
        await db.webhooks.update_one({"webhook_id": hook["webhook_id"]}, {"$set": {"enabled": True, "failure_count": 0}})
        result = await _deliver_webhook(hook, dl.get("payload") or {})
        if result.get("success"):
            await db.webhook_dead_letters.delete_one({"dead_letter_id": dead_letter_id})
        return result

    @api_router.delete("/webhooks/dead-letters/{dead_letter_id}")
    async def delete_dead_letter(dead_letter_id: str, request: Request):
        await get_current_user(request)
        await db.webhook_dead_letters.delete_one({"dead_letter_id": dead_letter_id})
        return {"deleted": dead_letter_id}

    # ============ Inbound Webhooks (trigger workflows) ============

    @api_router.post("/workspaces/{workspace_id}/inbound-webhooks")
    async def create_inbound_webhook(workspace_id: str, request: Request):
        """Create an inbound webhook that triggers a workflow"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        workflow_id = body.get("workflow_id")
        if not workflow_id:
            raise HTTPException(400, "workflow_id is required")

        import secrets
        token = secrets.token_urlsafe(24)
        hook_id = f"iwh_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        hook = {
            "inbound_hook_id": hook_id,
            "workspace_id": workspace_id,
            "workflow_id": workflow_id,
            "name": body.get("name", "Inbound Webhook"),
            "url_token": token,
            "secret": body.get("secret", ""),
            "is_active": True,
            "input_mapping": body.get("input_mapping") or {},
            "trigger_count": 0,
            "last_triggered": None,
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.inbound_webhooks.insert_one(hook)
        result = {k: v for k, v in hook.items() if k != "_id"}
        result["webhook_url"] = f"/api/webhooks/inbound/{token}"
        return result

    @api_router.get("/workspaces/{workspace_id}/inbound-webhooks")
    async def list_inbound_webhooks(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        hooks = await db.inbound_webhooks.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(20)
        for h in hooks:
            h["webhook_url"] = f"/api/webhooks/inbound/{h['url_token']}"
        return hooks

    @api_router.delete("/inbound-webhooks/{hook_id}")
    async def delete_inbound_webhook(hook_id: str, request: Request):
        user = await get_current_user(request)
        hook = await db.inbound_webhooks.find_one({"inbound_hook_id": hook_id}, {"workspace_id": 1})
        if not hook: raise HTTPException(404, "Not found")
        if hook.get("workspace_id"):
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, hook["workspace_id"])
        result = await db.inbound_webhooks.delete_one({"inbound_hook_id": hook_id})
        return {"message": "Deleted"}

    @api_router.post("/webhooks/inbound/{url_token}")
    async def receive_inbound_webhook(url_token: str, request: Request):
        """Public endpoint — triggers a workflow from external event"""
        hook = await db.inbound_webhooks.find_one({"url_token": url_token, "is_active": True}, {"_id": 0})
        if not hook:
            raise HTTPException(404, "Webhook not found or inactive")

        body = await request.json()

        # Apply input mapping
        mapped_input = {}
        mapping = hook.get("input_mapping") or {}
        if mapping:
            for wf_field, payload_path in mapping.items():
                # Simple dot-path extraction
                val = body
                for key in payload_path.strip("$.").split("."):
                    if isinstance(val, dict):
                        val = val.get(key)
                    else:
                        val = None
                        break
                if val is not None:
                    mapped_input[wf_field] = val
        else:
            mapped_input = body

        # Trigger the workflow
        import asyncio as _asyncio
        from workflow_engine import WorkflowOrchestrator, SSEManager
        workflow_id = hook["workflow_id"]
        run_id = f"wrun_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "run_id": run_id, "workflow_id": workflow_id, "status": "queued",
            "triggered_by": "webhook", "run_by": hook.get("created_by", "webhook"),
            "initial_input": mapped_input, "final_output": None,
            "current_node_id": None, "total_tokens": 0, "total_cost_usd": 0,
            "total_duration_ms": 0, "error_message": None, "started_at": None,
            "completed_at": None, "created_at": now,
        }
        await db.workflow_runs.insert_one(run)

        # Update trigger count
        await db.inbound_webhooks.update_one(
            {"inbound_hook_id": hook["inbound_hook_id"]},
            {"$inc": {"trigger_count": 1}, "$set": {"last_triggered": now}}
        )

        # Execute async
        sse = SSEManager()
        orchestrator = WorkflowOrchestrator(db, sse)
        _asyncio.create_task(orchestrator.execute_workflow(run_id))

        return {"status": "triggered", "run_id": run_id, "workflow_id": workflow_id}

    async def _deliver_webhook(hook, payload):
        """Deliver a webhook payload with retry policy"""
        delivery_id = f"whd_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        max_retries = (hook.get("retry_policy") or {}).get("max_retries", 3)
        retry_delays = [5, 30, 120]  # seconds: 5s, 30s, 2min
        attempt = 0
        status = 0
        success = False

        while attempt <= max_retries:
            try:
                import hmac
                import hashlib
                headers = {"Content-Type": "application/json", "X-Nexus-Webhook-Id": hook["webhook_id"], "X-Nexus-Attempt": str(attempt + 1)}
                if hook.get("secret"):
                    import json as _json
                    sig = hmac.new(hook["secret"].encode(), _json.dumps(payload, sort_keys=True, default=str).encode(), hashlib.sha256).hexdigest()
                    headers["X-Nexus-Signature"] = sig

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(hook["url"], json=payload, headers=headers)
                    status = resp.status_code
                    success = 200 <= status < 300
            except Exception as e:
                status = 0
                success = False
                logger.warning(f"Webhook delivery attempt {attempt+1} failed for {hook['webhook_id']}: {e}")

            if success:
                break
            attempt += 1
            if attempt <= max_retries:
                delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                await asyncio.sleep(delay)

        await db.webhook_deliveries.insert_one({
            "delivery_id": delivery_id, "webhook_id": hook["webhook_id"],
            "event": payload.get("event", "unknown"), "status_code": status,
            "success": success, "attempts": attempt + 1, "timestamp": now,
        })
        update = {"last_triggered_at": now, "last_status": status}
        if not success:
            update["failure_count"] = hook.get("failure_count", 0) + 1
            if update["failure_count"] >= 10:
                update["enabled"] = False
                # Move to dead-letter queue
                await db.webhook_dead_letters.insert_one({
                    "dead_letter_id": f"whdl_{uuid.uuid4().hex[:12]}",
                    "webhook_id": hook["webhook_id"],
                    "workspace_id": hook.get("workspace_id", ""),
                    "event": payload.get("event", "unknown"),
                    "payload": payload,
                    "last_status": status,
                    "attempts": attempt + 1,
                    "reason": "max_failures_exceeded",
                    "created_at": now,
                })
                logger.warning(f"Webhook {hook['webhook_id']} disabled and moved to dead-letter queue")
        else:
            update["failure_count"] = 0
        await db.webhooks.update_one({"webhook_id": hook["webhook_id"]}, {"$set": update})
        return {"success": success, "status_code": status, "delivery_id": delivery_id, "attempts": attempt + 1}


async def emit_webhook_event(db, workspace_id, event, data):
    """Emit an event to all registered webhooks for a workspace"""
    hooks = await db.webhooks.find(
        {"workspace_id": workspace_id, "enabled": True, "events": event}, {"_id": 0}
    ).to_list(10)
    payload = {"event": event, "workspace_id": workspace_id, "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
    for hook in hooks:
        asyncio.create_task(_deliver_single(db, hook, payload))


async def _deliver_single(db, hook, payload):
    """Deliver to a single webhook (background task)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(hook["url"], json=payload, headers={"Content-Type": "application/json", "X-Nexus-Webhook-Id": hook["webhook_id"]})
            success = 200 <= resp.status_code < 300
    except Exception as _e:
        logger.warning(f"Caught exception: {_e}")
        success = False
    now = datetime.now(timezone.utc).isoformat()
    await db.webhook_deliveries.insert_one({
        "delivery_id": f"whd_{uuid.uuid4().hex[:12]}", "webhook_id": hook["webhook_id"],
        "event": payload.get("event"), "status_code": getattr(resp, 'status_code', 0) if 'resp' in dir() else 0,
        "success": success, "timestamp": now,
    })
    update = {"last_triggered_at": now}
    if not success:
        await db.webhooks.update_one({"webhook_id": hook["webhook_id"]}, {"$inc": {"failure_count": 1}, "$set": update})
    else:
        await db.webhooks.update_one({"webhook_id": hook["webhook_id"]}, {"$set": {**update, "failure_count": 0}})
