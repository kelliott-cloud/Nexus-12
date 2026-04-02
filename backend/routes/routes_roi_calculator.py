"""AI Agent Model ROI Calculator — Cost analysis, model comparison, and forecast.
Aggregates from reporting_events and messages for real usage data."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Request

logger = logging.getLogger(__name__)

# Estimated cost per 1K tokens by model family (fallback when not tracked)
MODEL_COSTS = {
    "claude": {"input": 0.003, "output": 0.015},
    "gpt": {"input": 0.005, "output": 0.015},
    "gemini": {"input": 0.00025, "output": 0.001},
    "groq": {"input": 0.0003, "output": 0.0008},
    "deepseek": {"input": 0.0014, "output": 0.0028},
    "grok": {"input": 0.005, "output": 0.015},
    "perplexity": {"input": 0.001, "output": 0.001},
    "mistral": {"input": 0.002, "output": 0.006},
    "cohere": {"input": 0.0005, "output": 0.0015},
    "mercury": {"input": 0.001, "output": 0.003},
    "default": {"input": 0.002, "output": 0.006},
}


def _model_family(agent_key: str) -> str:
    key = (agent_key or "").lower()
    for family in MODEL_COSTS:
        if family in key:
            return family
    return "default"


def register_roi_calculator_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/roi/summary")
    async def roi_summary(ws_id: str, request: Request, period: str = "30d"):
        """Overall ROI summary: costs, volume, efficiency."""
        await get_current_user(request)
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Costs from reporting_events
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

        # Message volume from messages
        msg_pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": None,
                "total_messages": {"$sum": 1},
                "agent_messages": {"$sum": {"$cond": [{"$ifNull": ["$agent_key", False]}, 1, 0]}},
                "human_messages": {"$sum": {"$cond": [{"$ifNull": ["$agent_key", False]}, 0, 1]}},
            }}
        ]
        msg_data = {"total_messages": 0, "agent_messages": 0, "human_messages": 0}
        async for doc in db.messages.aggregate(msg_pipeline):
            msg_data = {k: doc.get(k, 0) for k in msg_data}

        total_tokens = cost_data["total_tokens_in"] + cost_data["total_tokens_out"]
        cost_per_message = round(cost_data["total_cost"] / max(msg_data["agent_messages"], 1), 4)
        cost_per_1k_tokens = round(cost_data["total_cost"] / max(total_tokens / 1000, 1), 4)

        # Estimated time saved (avg 2 min per AI response vs 15 min human equivalent)
        time_saved_hours = round(msg_data["agent_messages"] * 13 / 60, 1)
        human_cost_equivalent = round(time_saved_hours * 50, 2)  # $50/hr avg
        roi_multiplier = round(human_cost_equivalent / max(cost_data["total_cost"], 0.01), 1)

        return {
            "period": period,
            "costs": {
                "total_usd": round(cost_data["total_cost"], 2),
                "total_calls": cost_data["total_calls"],
                "total_tokens": total_tokens,
                "cost_per_message": cost_per_message,
                "cost_per_1k_tokens": cost_per_1k_tokens,
            },
            "volume": msg_data,
            "roi": {
                "time_saved_hours": time_saved_hours,
                "human_cost_equivalent_usd": human_cost_equivalent,
                "roi_multiplier": roi_multiplier,
                "efficiency_score": min(round(roi_multiplier / 10 * 100, 0), 100),
            },
        }

    @api_router.get("/workspaces/{ws_id}/roi/by-model")
    async def roi_by_model(ws_id: str, request: Request, period: str = "30d"):
        """Compare ROI across different AI models."""
        await get_current_user(request)
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
            {"$group": {
                "_id": "$agent_key",
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "tokens_in": {"$sum": "$tokens_in"},
                "tokens_out": {"$sum": "$tokens_out"},
                "calls": {"$sum": 1},
                "avg_latency_ms": {"$avg": "$latency_ms"},
            }},
            {"$sort": {"total_cost": -1}},
        ]

        models = []
        async for doc in db.reporting_events.aggregate(pipeline):
            model = doc["_id"] or "unknown"
            total_tokens = doc["tokens_in"] + doc["tokens_out"]
            cost = doc["total_cost"]
            family = _model_family(model)
            ref_cost = MODEL_COSTS.get(family, MODEL_COSTS["default"])

            models.append({
                "model": model,
                "family": family,
                "cost_usd": round(cost, 4),
                "calls": doc["calls"],
                "tokens_in": doc["tokens_in"],
                "tokens_out": doc["tokens_out"],
                "cost_per_call": round(cost / max(doc["calls"], 1), 4),
                "cost_per_1k_tokens": round(cost / max(total_tokens / 1000, 1), 4),
                "avg_latency_ms": round(doc["avg_latency_ms"] or 0),
                "ref_input_cost_1k": ref_cost["input"],
                "ref_output_cost_1k": ref_cost["output"],
            })

        return {"period": period, "models": models}

    @api_router.get("/workspaces/{ws_id}/roi/by-agent")
    async def roi_by_agent(ws_id: str, request: Request, period: str = "30d"):
        """Per-agent cost vs value analysis."""
        await get_current_user(request)
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Cost per agent from reporting
        cost_pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
            {"$group": {
                "_id": "$agent_key",
                "cost": {"$sum": "$estimated_cost_usd"},
                "calls": {"$sum": 1},
                "tokens": {"$sum": {"$add": ["$tokens_in", "$tokens_out"]}},
            }},
        ]
        cost_by_agent = {}
        async for doc in db.reporting_events.aggregate(cost_pipeline):
            cost_by_agent[doc["_id"]] = doc

        # Message count per agent
        msg_pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "agent_key": {"$exists": True}}},
            {"$group": {"_id": "$agent_key", "messages": {"$sum": 1}}},
        ]
        msg_by_agent = {}
        async for doc in db.messages.aggregate(msg_pipeline):
            msg_by_agent[doc["_id"]] = doc["messages"]

        agents = []
        all_keys = set(list(cost_by_agent.keys()) + list(msg_by_agent.keys()))
        for key in all_keys:
            cost_info = cost_by_agent.get(key, {"cost": 0, "calls": 0, "tokens": 0})
            msgs = msg_by_agent.get(key, 0)
            cost = cost_info.get("cost", 0)
            time_saved = round(msgs * 13 / 60, 1)
            value = round(time_saved * 50, 2)
            agents.append({
                "agent": key or "unknown",
                "cost_usd": round(cost, 4),
                "calls": cost_info.get("calls", 0),
                "messages": msgs,
                "tokens": cost_info.get("tokens", 0),
                "time_saved_hours": time_saved,
                "value_usd": value,
                "roi": round(value / max(cost, 0.01), 1),
            })

        agents.sort(key=lambda x: x["roi"], reverse=True)
        return {"period": period, "agents": agents}

    @api_router.get("/workspaces/{ws_id}/roi/forecast")
    async def roi_forecast(ws_id: str, request: Request, days_ahead: int = 30):
        """Project cost forecasting based on usage trends."""
        await get_current_user(request)
        # Get last 60 days of daily costs
        cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

        daily_pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
            {"$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "cost": {"$sum": "$estimated_cost_usd"},
                "calls": {"$sum": 1},
                "tokens": {"$sum": {"$add": ["$tokens_in", "$tokens_out"]}},
            }},
            {"$sort": {"_id": 1}},
        ]

        historical = []
        async for doc in db.reporting_events.aggregate(daily_pipeline):
            historical.append({
                "date": doc["_id"],
                "cost_usd": round(doc["cost"], 4),
                "calls": doc["calls"],
                "tokens": doc["tokens"],
            })

        # Simple linear regression for forecast
        if len(historical) >= 2:
            costs = [d["cost_usd"] for d in historical]
            n = len(costs)
            x_mean = (n - 1) / 2
            y_mean = sum(costs) / n
            numerator = sum((i - x_mean) * (costs[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            slope = numerator / max(denominator, 0.001)
            intercept = y_mean - slope * x_mean

            forecast = []
            last_date = datetime.strptime(historical[-1]["date"], "%Y-%m-%d")
            for d in range(1, days_ahead + 1):
                future_date = last_date + timedelta(days=d)
                predicted_cost = max(intercept + slope * (n + d - 1), 0)
                forecast.append({
                    "date": future_date.strftime("%Y-%m-%d"),
                    "predicted_cost_usd": round(predicted_cost, 4),
                })

            total_forecast = sum(f["predicted_cost_usd"] for f in forecast)
            trend = "increasing" if slope > 0.001 else "decreasing" if slope < -0.001 else "stable"
        else:
            forecast = []
            total_forecast = 0
            trend = "insufficient_data"
            slope = 0

        return {
            "historical": historical,
            "forecast": forecast,
            "days_ahead": days_ahead,
            "total_forecast_usd": round(total_forecast, 2),
            "daily_avg_forecast": round(total_forecast / max(days_ahead, 1), 4),
            "trend": trend,
            "trend_slope_per_day": round(slope, 6),
        }
