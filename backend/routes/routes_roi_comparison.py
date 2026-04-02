"""Multi-Workspace ROI Comparison Dashboard — compare costs, efficiency, and ROI across workspaces."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


def register_roi_comparison_routes(api_router, db, get_current_user):

    @api_router.get("/roi-comparison/workspaces")
    async def roi_comparison_data(request: Request, period: str = "30d"):
        """Get ROI data for all workspaces the user belongs to, for side-by-side comparison."""
        user = await get_current_user(request)
        user_id = user["user_id"]
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get all workspaces user belongs to
        memberships = await db.workspace_members.find(
            {"user_id": user_id}, {"_id": 0, "workspace_id": 1}
        ).to_list(50)
        ws_ids = [m["workspace_id"] for m in memberships]

        # Also check workspaces the user owns
        owned = await db.workspaces.find(
            {"owner_id": user_id}, {"_id": 0, "workspace_id": 1, "name": 1}
        ).to_list(50)
        for w in owned:
            if w["workspace_id"] not in ws_ids:
                ws_ids.append(w["workspace_id"])

        if not ws_ids:
            return {"period": period, "workspaces": []}

        # Fetch workspace names
        ws_map = {}
        for ws in await db.workspaces.find(
            {"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}
        ).to_list(50):
            ws_map[ws["workspace_id"]] = ws.get("name", ws["workspace_id"])

        results = []
        for ws_id in ws_ids:
            ws_name = ws_map.get(ws_id, ws_id)

            # Costs
            cost_pipeline = [
                {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
                {"$group": {
                    "_id": None,
                    "total_cost": {"$sum": "$estimated_cost_usd"},
                    "total_tokens_in": {"$sum": "$tokens_in"},
                    "total_tokens_out": {"$sum": "$tokens_out"},
                    "total_calls": {"$sum": 1},
                }}
            ]
            cost_data = {"total_cost": 0, "total_tokens_in": 0, "total_tokens_out": 0, "total_calls": 0}
            async for doc in db.reporting_events.aggregate(cost_pipeline):
                cost_data = {k: doc.get(k, 0) for k in cost_data}

            # Messages
            msg_pipeline = [
                {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}}},
                {"$group": {
                    "_id": None,
                    "total_messages": {"$sum": 1},
                    "agent_messages": {"$sum": {"$cond": [{"$ifNull": ["$agent_key", False]}, 1, 0]}},
                }}
            ]
            msg_data = {"total_messages": 0, "agent_messages": 0}
            async for doc in db.messages.aggregate(msg_pipeline):
                msg_data = {k: doc.get(k, 0) for k in msg_data}

            total_tokens = cost_data["total_tokens_in"] + cost_data["total_tokens_out"]
            time_saved_hours = round(msg_data["agent_messages"] * 13 / 60, 1)
            human_cost_equiv = round(time_saved_hours * 50, 2)
            roi_multiplier = round(human_cost_equiv / max(cost_data["total_cost"], 0.01), 1)

            # Agent count
            agent_count = await db.nexus_agents.count_documents({"workspace_id": ws_id})

            # Knowledge chunks
            knowledge_count = await db.agent_knowledge.count_documents({"workspace_id": ws_id, "flagged": {"$ne": True}})

            results.append({
                "workspace_id": ws_id,
                "workspace_name": ws_name,
                "total_cost_usd": round(cost_data["total_cost"], 2),
                "total_calls": cost_data["total_calls"],
                "total_tokens": total_tokens,
                "total_messages": msg_data["total_messages"],
                "agent_messages": msg_data["agent_messages"],
                "time_saved_hours": time_saved_hours,
                "human_cost_equivalent_usd": human_cost_equiv,
                "roi_multiplier": roi_multiplier,
                "efficiency_score": min(round(roi_multiplier / 10 * 100, 0), 100),
                "agent_count": agent_count,
                "knowledge_chunks": knowledge_count,
            })

        # Sort by ROI multiplier descending
        results.sort(key=lambda x: x["roi_multiplier"], reverse=True)
        return {"period": period, "workspaces": results}

    @api_router.get("/roi-comparison/trend")
    async def roi_comparison_trend(request: Request, period: str = "30d"):
        """Get daily cost trend for all user workspaces for comparison charting."""
        user = await get_current_user(request)
        user_id = user["user_id"]
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get workspace IDs
        memberships = await db.workspace_members.find(
            {"user_id": user_id}, {"_id": 0, "workspace_id": 1}
        ).to_list(50)
        ws_ids = [m["workspace_id"] for m in memberships]
        owned = await db.workspaces.find(
            {"owner_id": user_id}, {"_id": 0, "workspace_id": 1, "name": 1}
        ).to_list(50)
        for w in owned:
            if w["workspace_id"] not in ws_ids:
                ws_ids.append(w["workspace_id"])

        # Workspace names
        ws_map = {}
        for ws in await db.workspaces.find(
            {"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}
        ).to_list(50):
            ws_map[ws["workspace_id"]] = ws.get("name", ws["workspace_id"])

        trends = {}
        for ws_id in ws_ids:
            pipeline = [
                {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
                {"$group": {
                    "_id": {"$substr": ["$created_at", 0, 10]},
                    "cost": {"$sum": "$estimated_cost_usd"},
                    "calls": {"$sum": 1},
                }},
                {"$sort": {"_id": 1}},
            ]
            daily = []
            async for doc in db.reporting_events.aggregate(pipeline):
                daily.append({"date": doc["_id"], "cost_usd": round(doc["cost"], 4), "calls": doc["calls"]})
            trends[ws_id] = {
                "workspace_name": ws_map.get(ws_id, ws_id),
                "daily": daily,
            }

        return {"period": period, "trends": trends}
