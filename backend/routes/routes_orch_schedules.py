"""Batch Orchestration Scheduling — Schedule orchestrations to run on cron intervals."""
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)


class ScheduleOrchestration(BaseModel):
    orchestration_id: str
    input_text: str = Field(..., min_length=1)
    interval_minutes: int = Field(60, ge=5, le=43200)
    enabled: bool = True
    context: dict = {}


def register_orch_schedule_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/orchestration-schedules")
    async def create_schedule(ws_id: str, data: ScheduleOrchestration, request: Request):
        user = await _authed_user(request, ws_id)
        orch = await db.orchestrations.find_one({"orchestration_id": data.orchestration_id, "workspace_id": ws_id}, {"_id": 0, "name": 1})
        if not orch:
            raise HTTPException(404, "Orchestration not found")
        sched_id = f"osched_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        schedule = {
            "schedule_id": sched_id, "workspace_id": ws_id,
            "orchestration_id": data.orchestration_id, "orchestration_name": orch.get("name", ""),
            "input_text": data.input_text, "context": data.context,
            "interval_minutes": data.interval_minutes, "enabled": data.enabled,
            "last_run_at": None, "next_run_at": now, "run_count": 0,
            "created_by": user["user_id"], "created_at": now,
        }
        await db.orchestration_schedules.insert_one(schedule)
        schedule.pop("_id", None)
        return schedule

    @api_router.get("/workspaces/{ws_id}/orchestration-schedules")
    async def list_schedules(ws_id: str, request: Request):
        user = await _authed_user(request, ws_id)
        schedules = await db.orchestration_schedules.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"schedules": schedules}

    @api_router.put("/workspaces/{ws_id}/orchestration-schedules/{sched_id}")
    async def update_schedule(ws_id: str, sched_id: str, request: Request):
        user = await _authed_user(request, ws_id)
        body = await request.json()
        updates = {}
        if "enabled" in body:
            updates["enabled"] = body["enabled"]
        if "interval_minutes" in body:
            updates["interval_minutes"] = max(5, min(43200, body["interval_minutes"]))
        if "input_text" in body:
            updates["input_text"] = body["input_text"]
        if updates:
            await db.orchestration_schedules.update_one({"schedule_id": sched_id}, {"$set": updates})
        sched = await db.orchestration_schedules.find_one({"schedule_id": sched_id}, {"_id": 0})
        return sched or {"error": "Not found"}

    @api_router.delete("/workspaces/{ws_id}/orchestration-schedules/{sched_id}")
    async def delete_schedule(ws_id: str, sched_id: str, request: Request):
        user = await _authed_user(request, ws_id)
        await db.orchestration_schedules.delete_one({"schedule_id": sched_id})
        return {"deleted": sched_id}


async def run_orchestration_schedules(db):
    """Background task: check and run due orchestration schedules."""
    from routes.routes_orchestration import _execute_orchestration
    now = datetime.now(timezone.utc).isoformat()
    due = await db.orchestration_schedules.find(
        {"enabled": True, "next_run_at": {"$lte": now}}, {"_id": 0}
    ).to_list(10)

    for sched in due:
        try:
            orch = await db.orchestrations.find_one(
                {"orchestration_id": sched["orchestration_id"]}, {"_id": 0}
            )
            if not orch:
                continue
            run_id = f"orun_{uuid.uuid4().hex[:10]}"
            run = {
                "run_id": run_id, "orchestration_id": sched["orchestration_id"],
                "orchestration_name": orch["name"], "workspace_id": sched["workspace_id"],
                "started_by": "scheduler", "input_text": sched["input_text"],
                "context": sched.get("context") or {},
                "status": "running", "step_results": [], "final_output": "",
                "started_at": now, "completed_at": None,
            }
            await db.orchestration_runs.insert_one(run)
            asyncio.create_task(_execute_orchestration(db, run_id, orch, sched["input_text"], sched.get("context") or {}, sched["workspace_id"]))

            from datetime import timedelta
            next_run = (datetime.now(timezone.utc) + timedelta(minutes=sched["interval_minutes"])).isoformat()
            await db.orchestration_schedules.update_one(
                {"schedule_id": sched["schedule_id"]},
                {"$set": {"last_run_at": now, "next_run_at": next_run}, "$inc": {"run_count": 1}}
            )
            logger.info(f"Scheduled orchestration {sched['orchestration_id']} run: {run_id}")
        except Exception as e:
            logger.error(f"Scheduled orchestration failed: {e}")
