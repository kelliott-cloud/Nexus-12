import uuid
import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from typing import Optional


def calculate_code_quality(content):
    """Score code quality based on heuristics (0-100)"""
    if not content or "```" not in content:
        return 0

    score = 40
    blocks = content.split("```")

    for i in range(1, len(blocks), 2):
        block = blocks[i] if i < len(blocks) else ""
        lines = [l for l in block.split('\n') if l.strip()]

        # Language annotation
        first_line = block.strip().split('\n')[0].strip() if block.strip() else ""
        if first_line and first_line.replace('-', '').replace('+', '').isalpha():
            score += 4

        # Comments
        if any(c in block for c in ['//', '#', '/*', '"""', "'''"]):
            score += 6

        # Error handling
        if any(k in block for k in ['try', 'catch', 'except', 'finally', 'throw', 'raise']):
            score += 6

        # Type hints / annotations
        if any(k in block for k in ['-> ', ': str', ': int', ': bool', ': float', ': list', ': dict', 'TypeScript', 'interface ']):
            score += 5

        # Functions/classes
        if any(k in block for k in ['def ', 'function ', 'class ', 'const ', 'async ']):
            score += 5

        # Proper structure (multiple lines)
        if len(lines) > 5:
            score += 4
        if len(lines) > 15:
            score += 5

        # Imports (shows awareness of dependencies)
        if any(k in block for k in ['import ', 'require(', 'from ']):
            score += 3

    return min(score, 100)


def register_analytics_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    @api_router.get("/workspaces/{workspace_id}/analytics")
    async def get_analytics(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)

        # Get analytics data (limit to last 500 for performance)
        analytics = await db.analytics.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(500)

        # Get channels for context
        channels = await db.channels.find(
            {"workspace_id": workspace_id}, {"_id": 0, "channel_id": 1, "name": 1}
        ).to_list(100)
        channel_map = {ch["channel_id"]: ch.get("name", "unknown") for ch in channels}

        # Aggregate per model
        model_stats = {}
        timeline_data = {}

        for a in analytics:
            agent = a.get("agent", "unknown")
            if agent not in model_stats:
                model_stats[agent] = {
                    "total_responses": 0,
                    "total_response_time_ms": 0,
                    "total_code_blocks": 0,
                    "total_code_quality": 0,
                    "code_quality_count": 0,
                    "total_content_length": 0,
                    "response_times": []
                }

            s = model_stats[agent]
            s["total_responses"] += 1
            s["total_response_time_ms"] += a.get("response_time_ms", 0)
            s["total_code_blocks"] += a.get("code_blocks", 0)
            s["total_content_length"] += a.get("content_length", 0)
            s["response_times"].append(a.get("response_time_ms", 0))

            cq = a.get("code_quality_score", 0)
            if cq > 0:
                s["total_code_quality"] += cq
                s["code_quality_count"] += 1

            # Timeline (group by hour)
            ts = a.get("timestamp", "")
            if ts:
                hour_key = ts[:13]
                if hour_key not in timeline_data:
                    timeline_data[hour_key] = {"timestamp": hour_key, "count": 0}
                timeline_data[hour_key]["count"] += 1

        # Compute derived stats
        model_comparison = []
        for agent, s in model_stats.items():
            avg_time = s["total_response_time_ms"] / max(s["total_responses"], 1)
            avg_quality = s["total_code_quality"] / max(s["code_quality_count"], 1)
            p95_time = sorted(s["response_times"])[int(len(s["response_times"]) * 0.95)] if s["response_times"] else 0

            model_comparison.append({
                "agent": agent,
                "total_responses": s["total_responses"],
                "avg_response_time_ms": round(avg_time),
                "p95_response_time_ms": p95_time,
                "avg_code_quality": round(avg_quality, 1),
                "total_code_blocks": s["total_code_blocks"],
                "avg_content_length": round(s["total_content_length"] / max(s["total_responses"], 1)),
            })

        # Sort timeline
        timeline = sorted(timeline_data.values(), key=lambda x: x["timestamp"])

        # Collaboration patterns
        messages = await db.messages.find(
            {"channel_id": {"$in": list(channel_map.keys())}},
            {"_id": 0, "sender_type": 1, "ai_model": 1, "created_at": 1}
        ).sort("created_at", -1).limit(1000).to_list(500)

        # Count message pairs (which model follows which)
        patterns = {}
        prev_model = None
        for m in sorted(messages, key=lambda x: x.get("created_at", "")):
            if m["sender_type"] == "ai":
                curr = m.get("ai_model")
                if prev_model and curr and prev_model != curr:
                    key = f"{prev_model}->{curr}"
                    patterns[key] = patterns.get(key, 0) + 1
                prev_model = curr
            else:
                prev_model = None

        # Top collaboration pairs
        top_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:10]

        # Overall stats
        total_collabs = len(set(a.get("channel_id", "") + "_" + a.get("timestamp", "")[:16] for a in analytics))
        total_responses = sum(s["total_responses"] for s in model_stats.values())
        avg_response_time = sum(s["total_response_time_ms"] for s in model_stats.values()) / max(total_responses, 1)

        # Top performer (fastest avg response)
        top_performer = min(model_comparison, key=lambda x: x["avg_response_time_ms"]) if model_comparison else None

        return {
            "overview": {
                "total_collaborations": total_collabs,
                "total_ai_responses": total_responses,
                "avg_response_time_ms": round(avg_response_time),
                "top_performer": top_performer["agent"] if top_performer else None,
            },
            "model_comparison": model_comparison,
            "timeline": timeline,
            "collaboration_patterns": [{"pair": p[0], "count": p[1]} for p in top_patterns],
            "channels_analyzed": len(channel_map),
        }

    @api_router.get("/workspaces/{workspace_id}/analytics/models")
    async def get_model_details(workspace_id: str, request: Request, agent: Optional[str] = None):
        user = await _authed_user(request, workspace_id)

        query = {"workspace_id": workspace_id}
        if agent:
            query["agent"] = agent

        analytics = await db.analytics.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).to_list(100)

        return analytics
