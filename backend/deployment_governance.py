from nexus_utils import safe_regex
"""Deployment Governance — Policy enforcement for autonomous deployments.

Checks cost limits, tool restrictions, human approval gates, and auto-pause thresholds.
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


async def check_policy(db, deployment, run, tool_name, estimated_cost=0):
    """Check if a tool call is allowed by the deployment's policy.
    
    Returns: {"action": "allow"|"block"|"escalate", "reason": str}
    """
    policy = deployment.get("policy") or {}
    
    # 1. Check blocked tools
    blocked = policy.get("blocked_tools") or []
    if tool_name in blocked:
        return {"action": "block", "reason": f"Tool '{tool_name}' is blocked by policy"}
    
    # 2. Check if tool requires human approval
    require_approval = policy.get("require_human_approval") or []
    if tool_name in require_approval:
        return {"action": "escalate", "reason": f"Tool '{tool_name}' requires human approval"}
    
    # 3. Check max actions per run
    max_actions = policy.get("max_actions_per_run", 0)
    if max_actions > 0 and run.get("actions_taken", 0) >= max_actions:
        return {"action": "block", "reason": f"Max actions per run ({max_actions}) reached"}
    
    # 4. Check max cost per run
    max_cost_run = policy.get("max_cost_per_run_usd", 0)
    if max_cost_run > 0 and (run.get("cost_usd", 0) + estimated_cost) > max_cost_run:
        return {"action": "block", "reason": f"Cost limit per run (${max_cost_run}) would be exceeded"}
    
    # 5. Check max cost per day
    max_cost_day = policy.get("max_cost_per_day_usd", 0)
    if max_cost_day > 0:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_cost = 0
        runs_today = await db.deployment_runs.find({
            "deployment_id": deployment.get("deployment_id"),
            "created_at": {"$regex": f"^{safe_regex(today)}"}
        }, {"_id": 0, "cost_usd": 1}).to_list(100)
        daily_cost = sum(r.get("cost_usd", 0) for r in runs_today)
        if (daily_cost + estimated_cost) > max_cost_day:
            return {"action": "block", "reason": f"Daily cost limit (${max_cost_day}) would be exceeded"}
    
    # 6. Check allowed tools whitelist (skip for AI inference - that's always allowed)
    allowed = deployment.get("allowed_tools") or []
    if allowed and tool_name not in allowed and tool_name != "ai_inference":
        return {"action": "block", "reason": f"Tool '{tool_name}' not in allowed tools list"}
    
    return {"action": "allow", "reason": ""}


async def check_auto_pause(db, deployment_id):
    """Check if deployment should auto-pause due to error threshold."""
    deployment = await db.deployments.find_one(
        {"deployment_id": deployment_id}, {"_id": 0, "policy": 1, "status": 1}
    )
    if not deployment or deployment.get("status") != "active":
        return False
    
    policy = deployment.get("policy") or {}
    threshold = policy.get("auto_pause_on_error_count", 0)
    if threshold <= 0:
        return False
    
    # Count recent consecutive failures
    recent_runs = await db.deployment_runs.find(
        {"deployment_id": deployment_id},
        {"_id": 0, "status": 1}
    ).sort("created_at", -1).limit(threshold).to_list(threshold)
    
    if len(recent_runs) >= threshold and all(r.get("status") == "failed" for r in recent_runs):
        await db.deployments.update_one(
            {"deployment_id": deployment_id},
            {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        logger.warning(f"Deployment {deployment_id} auto-paused after {threshold} consecutive failures")
        return True
    return False
