"""Agent Schedules - cron-like scheduled actions for AI agents in workspaces"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Preset action prompts
ACTION_PROMPTS = {
    "project_review": """Review all projects in this workspace. For each active project:
- Summarize current status and progress
- Identify any blockers or overdue tasks
- Suggest next steps or priority actions
- Flag any tasks that need reassignment
Use the list_projects and list_tasks tools to gather data, then provide a concise summary.""",

    "task_triage": """Triage all tasks across projects in this workspace:
- Identify unassigned tasks and suggest assignments
- Flag overdue or stale tasks (stuck in same status too long)
- Prioritize tasks that are blocking others
- Update task statuses where appropriate using update_task_status
Use list_projects and list_tasks tools to gather data, then take action.""",

    "standup_summary": """Generate a daily standup summary for this workspace:
- What was completed recently (tasks moved to 'done')
- What's currently in progress
- Any blockers or issues
- Key priorities for today
Use list_projects and list_tasks tools to gather current state.""",
}

VALID_ACTION_TYPES = ["project_review", "task_triage", "standup_summary", "custom"]
VALID_INTERVALS = [15, 30, 60, 120, 240, 480, 720, 1440]  # minutes


class ScheduleCreate(BaseModel):
    channel_id: str
    agent_key: str
    action_type: str = "project_review"
    custom_prompt: Optional[str] = None
    interval_minutes: int = 1440  # default: daily
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    action_type: Optional[str] = None
    custom_prompt: Optional[str] = None
    interval_minutes: Optional[int] = None
    enabled: Optional[bool] = None


def register_agent_schedule_routes(api_router, db, get_current_user, AI_MODELS):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.get("/workspaces/{workspace_id}/schedules")
    async def list_schedules(workspace_id: str, request: Request):
        """List all agent schedules for a workspace"""
        user = await _authed_user(request, workspace_id)
        schedules = await db.agent_schedules.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return schedules

    @api_router.post("/workspaces/{workspace_id}/schedules")
    async def create_schedule(workspace_id: str, data: ScheduleCreate, request: Request):
        """Create a new agent schedule"""
        user = await _authed_user(request, workspace_id)

        if data.action_type not in VALID_ACTION_TYPES:
            raise HTTPException(400, f"Invalid action_type. Use: {', '.join(VALID_ACTION_TYPES)}")
        if data.action_type == "custom" and not data.custom_prompt:
            raise HTTPException(400, "custom_prompt is required for 'custom' action type")
        if data.interval_minutes not in VALID_INTERVALS:
            raise HTTPException(400, f"Invalid interval. Use one of: {VALID_INTERVALS}")

        # Verify channel exists and has the agent
        channel = await db.channels.find_one({"channel_id": data.channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        if channel.get("workspace_id") != workspace_id:
            raise HTTPException(400, "Channel does not belong to this workspace")

        # Resolve agent name
        agent_name = data.agent_key
        is_nexus = data.agent_key.startswith("nxa_")
        if is_nexus:
            nxa = await db.nexus_agents.find_one({"agent_id": data.agent_key}, {"_id": 0})
            agent_name = nxa["name"] if nxa else data.agent_key
        elif data.agent_key in AI_MODELS:
            agent_name = AI_MODELS[data.agent_key]["name"]

        now = datetime.now(timezone.utc)
        schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
        next_run = now + timedelta(minutes=data.interval_minutes)

        schedule = {
            "schedule_id": schedule_id,
            "workspace_id": workspace_id,
            "channel_id": data.channel_id,
            "channel_name": channel.get("name", ""),
            "agent_key": data.agent_key,
            "agent_name": agent_name,
            "action_type": data.action_type,
            "custom_prompt": data.custom_prompt if data.action_type == "custom" else None,
            "interval_minutes": data.interval_minutes,
            "enabled": data.enabled,
            "last_run_at": None,
            "next_run_at": next_run.isoformat(),
            "run_count": 0,
            "last_status": None,
            "created_by": user["user_id"],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        await db.agent_schedules.insert_one(schedule)
        result = await db.agent_schedules.find_one({"schedule_id": schedule_id}, {"_id": 0})
        return result

    @api_router.put("/schedules/{schedule_id}")
    async def update_schedule(schedule_id: str, data: ScheduleUpdate, request: Request):
        """Update an agent schedule"""
        await get_current_user(request)
        schedule = await db.agent_schedules.find_one({"schedule_id": schedule_id})
        if not schedule:
            raise HTTPException(404, "Schedule not found")

        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.action_type is not None:
            if data.action_type not in VALID_ACTION_TYPES:
                raise HTTPException(400, f"Invalid action_type. Use: {', '.join(VALID_ACTION_TYPES)}")
            updates["action_type"] = data.action_type
        if data.custom_prompt is not None:
            updates["custom_prompt"] = data.custom_prompt
        if data.interval_minutes is not None:
            if data.interval_minutes not in VALID_INTERVALS:
                raise HTTPException(400, f"Invalid interval. Use one of: {VALID_INTERVALS}")
            updates["interval_minutes"] = data.interval_minutes
            updates["next_run_at"] = (datetime.now(timezone.utc) + timedelta(minutes=data.interval_minutes)).isoformat()
        if data.enabled is not None:
            updates["enabled"] = data.enabled
            if data.enabled and not schedule.get("enabled"):
                interval = data.interval_minutes or schedule.get("interval_minutes", 1440)
                updates["next_run_at"] = (datetime.now(timezone.utc) + timedelta(minutes=interval)).isoformat()

        await db.agent_schedules.update_one({"schedule_id": schedule_id}, {"$set": updates})
        result = await db.agent_schedules.find_one({"schedule_id": schedule_id}, {"_id": 0})
        return result

    @api_router.delete("/schedules/{schedule_id}")
    async def delete_schedule(schedule_id: str, request: Request):
        """Delete an agent schedule"""
        user = await get_current_user(request)
        sched = await db.agent_schedules.find_one({"schedule_id": schedule_id}, {"workspace_id": 1})
        if sched and sched.get("workspace_id"):
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, sched["workspace_id"])
        result = await db.agent_schedules.delete_one({"schedule_id": schedule_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Schedule not found")
        return {"message": "Schedule deleted"}

    @api_router.post("/schedules/{schedule_id}/run")
    async def trigger_schedule_now(schedule_id: str, request: Request):
        """Manually trigger a scheduled action immediately"""
        user = await get_current_user(request)
        schedule = await db.agent_schedules.find_one({"schedule_id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(404, "Schedule not found")
        if schedule.get("workspace_id"):
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, schedule["workspace_id"])

        asyncio.create_task(
            execute_scheduled_action(db, schedule, user["user_id"], AI_MODELS)
        )
        return {"status": "triggered", "schedule_id": schedule_id}

    @api_router.get("/schedules/{schedule_id}/history")
    async def get_schedule_history(schedule_id: str, request: Request):
        """Get execution history for a schedule"""
        await get_current_user(request)
        history = await db.schedule_runs.find(
            {"schedule_id": schedule_id}, {"_id": 0}
        ).sort("started_at", -1).to_list(20)
        return history

    @api_router.get("/schedules/action-types")
    async def get_action_types(request: Request):
        """Get available schedule action types"""
        await get_current_user(request)
        return {
            "action_types": [
                {"key": "project_review", "name": "Project Review", "description": "Review all projects, identify blockers, suggest next steps"},
                {"key": "task_triage", "name": "Task Triage", "description": "Check unassigned/overdue tasks, auto-assign or flag issues"},
                {"key": "standup_summary", "name": "Standup Summary", "description": "Daily summary of project progress and priorities"},
                {"key": "custom", "name": "Custom Action", "description": "Run a custom prompt on a schedule"},
            ],
            "valid_intervals": [
                {"minutes": 15, "label": "Every 15 min"},
                {"minutes": 30, "label": "Every 30 min"},
                {"minutes": 60, "label": "Hourly"},
                {"minutes": 120, "label": "Every 2 hours"},
                {"minutes": 240, "label": "Every 4 hours"},
                {"minutes": 480, "label": "Every 8 hours"},
                {"minutes": 720, "label": "Every 12 hours"},
                {"minutes": 1440, "label": "Daily"},
            ],
        }


async def execute_scheduled_action(db, schedule, user_id, AI_MODELS):
    """Execute a scheduled agent action"""
    from routes_ai_tools import TOOL_PROMPT, parse_tool_calls, strip_tool_calls, execute_tool

    schedule_id = schedule["schedule_id"]
    channel_id = schedule["channel_id"]
    workspace_id = schedule["workspace_id"]
    agent_key = schedule["agent_key"]
    now = datetime.now(timezone.utc)

    run_id = f"srun_{uuid.uuid4().hex[:12]}"
    run_record = {
        "run_id": run_id,
        "schedule_id": schedule_id,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "agent_key": agent_key,
        "action_type": schedule["action_type"],
        "status": "running",
        "started_at": now.isoformat(),
        "completed_at": None,
        "tool_calls_count": 0,
        "error": None,
    }
    await db.schedule_runs.insert_one(run_record)

    try:
        from ai_providers import call_ai_direct

        # Resolve agent model config
        is_nexus = agent_key.startswith("nxa_")
        if is_nexus:
            nexus_agent = await db.nexus_agents.find_one({"agent_id": agent_key}, {"_id": 0})
            if not nexus_agent:
                raise Exception(f"Nexus agent {agent_key} not found")
            base_model_key = nexus_agent["base_model"]
            if base_model_key not in AI_MODELS:
                raise Exception(f"Base model {base_model_key} not found")
            base_config = AI_MODELS[base_model_key]
            system_prompt = nexus_agent["system_prompt"]
            agent_name = nexus_agent["name"]
            effective_key = base_model_key
        else:
            if agent_key not in AI_MODELS:
                raise Exception(f"Agent {agent_key} not found")
            base_config = AI_MODELS[agent_key]
            system_prompt = base_config["system_prompt"]
            agent_name = base_config["name"]
            effective_key = agent_key

        # Get API key
        from server import get_ai_key_for_agent
        user_api_key, key_source = await get_ai_key_for_agent(user_id, workspace_id, effective_key)
        if not user_api_key:
            raise Exception(f"No API key available for {agent_name}")

        # Build the action prompt
        action_type = schedule["action_type"]
        if action_type == "custom":
            action_prompt = schedule.get("custom_prompt", "Analyze the workspace and provide insights.")
        else:
            action_prompt = ACTION_PROMPTS.get(action_type, ACTION_PROMPTS["project_review"])

        full_system = system_prompt + TOOL_PROMPT
        user_prompt = f"""=== SCHEDULED ACTION: {action_type.upper().replace('_', ' ')} ===
Workspace: {workspace_id}

{action_prompt}

Execute this action now. Use available tools to gather data and take actions as needed.
Provide a clear, concise summary of findings and any actions taken."""

        # Post a system message indicating the scheduled run started
        start_msg = {
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "system",
            "sender_id": "scheduler",
            "sender_name": "Scheduler",
            "content": f"_Scheduled **{action_type.replace('_', ' ').title()}** by {agent_name} starting..._",
            "created_at": now.isoformat(),
        }
        await db.messages.insert_one(start_msg)

        # Call the AI
        response_text = await call_ai_direct(effective_key, user_api_key, full_system, user_prompt,
                                             workspace_id=workspace_id, db=db, channel_id=channel_id)

        # Parse tool calls
        tool_calls = parse_tool_calls(response_text)
        visible_text = strip_tool_calls(response_text) if tool_calls else response_text

        # Post the AI response
        ai_msg = {
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "ai",
            "sender_id": agent_key,
            "sender_name": agent_name,
            "ai_model": agent_key if not is_nexus else agent_key,
            "content": visible_text,
            "tool_calls": [{"tool": tc.get("tool"), "params": tc.get("params") or {}} for tc in tool_calls] if tool_calls else None,
            "scheduled_action": action_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.messages.insert_one(ai_msg)

        # Execute tool calls
        for tc in tool_calls:
            result = await execute_tool(db, tc, workspace_id, agent_name, channel_id)
            tool_msg = {
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": channel_id,
                "sender_type": "tool",
                "sender_id": agent_key,
                "sender_name": agent_name,
                "ai_model": agent_key,
                "content": result["message"],
                "tool_result": result,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.messages.insert_one(tool_msg)

        # Update run record
        completed_at = datetime.now(timezone.utc)
        await db.schedule_runs.update_one(
            {"run_id": run_id},
            {"$set": {
                "status": "completed",
                "completed_at": completed_at.isoformat(),
                "tool_calls_count": len(tool_calls),
            }}
        )

        # Update schedule
        next_run = completed_at + timedelta(minutes=schedule["interval_minutes"])
        await db.agent_schedules.update_one(
            {"schedule_id": schedule_id},
            {"$set": {
                "last_run_at": completed_at.isoformat(),
                "next_run_at": next_run.isoformat(),
                "last_status": "completed",
                "updated_at": completed_at.isoformat(),
            },
            "$inc": {"run_count": 1}}
        )

        logger.info(f"Schedule {schedule_id} completed: {len(tool_calls)} tool calls")

    except Exception as e:
        logger.error(f"Schedule execution error ({schedule_id}): {e}")
        error_time = datetime.now(timezone.utc)
        await db.schedule_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed", "completed_at": error_time.isoformat(), "error": str(e)}}
        )
        next_run = error_time + timedelta(minutes=schedule["interval_minutes"])
        await db.agent_schedules.update_one(
            {"schedule_id": schedule_id},
            {"$set": {
                "last_run_at": error_time.isoformat(),
                "next_run_at": next_run.isoformat(),
                "last_status": "failed",
                "updated_at": error_time.isoformat(),
            },
            "$inc": {"run_count": 1}}
        )
        # Post error message
        err_msg = {
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "system",
            "sender_id": "scheduler",
            "sender_name": "Scheduler",
            "content": f"_Scheduled action failed: {str(e)}_",
            "created_at": error_time.isoformat(),
        }
        await db.messages.insert_one(err_msg)


async def execute_due_schedules(db, AI_MODELS) -> int:
    """Run one pass of the schedule checker. Returns count of schedules executed.
    Safe for external triggers (Cloud Scheduler / HTTP cron) — no infinite loop."""
    count = 0
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        due_schedules = await db.agent_schedules.find(
            {"enabled": True, "next_run_at": {"$lte": now_iso}},
            {"_id": 0}
        ).to_list(10)

        for schedule in due_schedules:
            claimed = await db.agent_schedules.update_one(
                {
                    "schedule_id": schedule["schedule_id"],
                    "next_run_at": schedule["next_run_at"],
                },
                {"$set": {
                    "next_run_at": (now + timedelta(minutes=schedule["interval_minutes"])).isoformat(),
                }}
            )
            if claimed.modified_count == 1:
                logger.info(f"Executing due schedule: {schedule['schedule_id']}")
                asyncio.create_task(
                    execute_scheduled_action(db, schedule, schedule["created_by"], AI_MODELS)
                )
                count += 1
    except Exception as e:
        logger.error(f"Schedule checker error: {e}")
    return count


async def run_schedule_checker(db, AI_MODELS):
    """Background loop that checks for and executes due schedules.
    Delegates to execute_due_schedules() each iteration."""
    logger.info("Schedule checker started")
    while True:
        await execute_due_schedules(db, AI_MODELS)
        await asyncio.sleep(60)
