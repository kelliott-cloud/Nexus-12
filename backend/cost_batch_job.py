"""Cost Snapshot Batch Job — Computes real per-model cost aggregates on a schedule.

Runs hourly via server.py startup background task.
Reads from reporting_events, applies PROVIDER_PRICING rates, stores snapshots in cost_snapshots.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("cost_batch")

# Provider pricing per 1M tokens (USD) — matches nexus_config.PROVIDER_PRICING
PRICING = {
    "anthropic": {"input": 15.0, "output": 75.0},
    "openai": {"input": 10.0, "output": 30.0},
    "gemini": {"input": 1.25, "output": 5.0},
    "deepseek": {"input": 0.14, "output": 0.28},
    "xai": {"input": 3.0, "output": 15.0},
    "cohere": {"input": 2.5, "output": 10.0},
    "groq": {"input": 0.27, "output": 1.10},
    "meta": {"input": 0.18, "output": 0.18},
    "mistral": {"input": 2.0, "output": 6.0},
    "perplexity": {"input": 1.0, "output": 1.0},
    "mercury": {"input": 0.50, "output": 1.50},
    "inflection": {"input": 0.40, "output": 1.20},
    "manus": {"input": 0.30, "output": 0.90},
    "qwen": {"input": 0.50, "output": 1.50},
    "moonshot": {"input": 0.55, "output": 1.65},
    "zhipu": {"input": 0.72, "output": 2.30},
    "cursor": {"input": 0.50, "output": 1.50},
    "google": {"input": 1.25, "output": 5.0},
    "github": {"input": 0.50, "output": 1.50},
}


def compute_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Compute actual cost in USD for given token counts."""
    rates = PRICING.get(provider, {"input": 1.0, "output": 3.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


async def run_cost_snapshot(db) -> None:
    """Compute and store cost snapshots for all workspaces.

    Aggregates reporting_events from the last 24h, groups by workspace+provider+model,
    computes actual costs, and upserts into cost_snapshots collection.
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    try:
        # Aggregate by workspace + provider + model for last 24h
        pipeline_24h = [
            {"$match": {"event_type": "ai_call", "created_at": {"$gte": cutoff_24h}}},
            {"$group": {
                "_id": {"workspace_id": "$workspace_id", "provider": "$provider", "model": "$model_name"},
                "calls": {"$sum": 1},
                "input_tokens": {"$sum": "$input_tokens"},
                "output_tokens": {"$sum": "$output_tokens"},
                "estimated_total": {"$sum": "$estimated_cost_usd"},
            }},
        ]

        # Aggregate by workspace + provider + model for current month
        pipeline_month = [
            {"$match": {"event_type": "ai_call", "created_at": {"$gte": month_start}}},
            {"$group": {
                "_id": {"workspace_id": "$workspace_id", "provider": "$provider", "model": "$model_name"},
                "calls": {"$sum": 1},
                "input_tokens": {"$sum": "$input_tokens"},
                "output_tokens": {"$sum": "$output_tokens"},
                "estimated_total": {"$sum": "$estimated_cost_usd"},
            }},
        ]

        # Process 24h data
        count_24h = 0
        async for doc in db.reporting_events.aggregate(pipeline_24h):
            ws = doc["_id"]["workspace_id"]
            provider = doc["_id"]["provider"] or "unknown"
            model = doc["_id"]["model"] or "unknown"
            actual_cost = compute_cost(provider, doc["input_tokens"], doc["output_tokens"])

            await db.cost_snapshots.update_one(
                {"workspace_id": ws, "provider": provider, "model": model, "period": "24h"},
                {"$set": {
                    "calls": doc["calls"],
                    "input_tokens": doc["input_tokens"],
                    "output_tokens": doc["output_tokens"],
                    "estimated_cost_usd": round(doc["estimated_total"], 6),
                    "actual_cost_usd": round(actual_cost, 6),
                    "computed_at": now.isoformat(),
                }},
                upsert=True,
            )
            count_24h += 1

        # Process monthly data
        count_month = 0
        async for doc in db.reporting_events.aggregate(pipeline_month):
            ws = doc["_id"]["workspace_id"]
            provider = doc["_id"]["provider"] or "unknown"
            model = doc["_id"]["model"] or "unknown"
            actual_cost = compute_cost(provider, doc["input_tokens"], doc["output_tokens"])

            await db.cost_snapshots.update_one(
                {"workspace_id": ws, "provider": provider, "model": model, "period": "monthly"},
                {"$set": {
                    "calls": doc["calls"],
                    "input_tokens": doc["input_tokens"],
                    "output_tokens": doc["output_tokens"],
                    "estimated_cost_usd": round(doc["estimated_total"], 6),
                    "actual_cost_usd": round(actual_cost, 6),
                    "computed_at": now.isoformat(),
                    "month": now.strftime("%Y-%m"),
                }},
                upsert=True,
            )
            count_month += 1

        # Build per-workspace totals
        ws_pipeline = [
            {"$match": {"period": "monthly"}},
            {"$group": {
                "_id": "$workspace_id",
                "total_actual_cost": {"$sum": "$actual_cost_usd"},
                "total_estimated_cost": {"$sum": "$estimated_cost_usd"},
                "total_calls": {"$sum": "$calls"},
                "total_input_tokens": {"$sum": "$input_tokens"},
                "total_output_tokens": {"$sum": "$output_tokens"},
            }},
        ]
        async for doc in db.cost_snapshots.aggregate(ws_pipeline):
            await db.cost_snapshots.update_one(
                {"workspace_id": doc["_id"], "period": "monthly_total"},
                {"$set": {
                    "total_actual_cost_usd": round(doc["total_actual_cost"], 4),
                    "total_estimated_cost_usd": round(doc["total_estimated_cost"], 4),
                    "total_calls": doc["total_calls"],
                    "total_input_tokens": doc["total_input_tokens"],
                    "total_output_tokens": doc["total_output_tokens"],
                    "computed_at": now.isoformat(),
                }},
                upsert=True,
            )

        if count_24h > 0 or count_month > 0:
            logger.info(f"Cost snapshot: {count_24h} 24h records, {count_month} monthly records")

    except Exception as e:
        logger.error(f"Cost snapshot batch failed: {e}")
