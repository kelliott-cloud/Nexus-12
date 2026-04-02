"""Model Performance & Disagreement Resolution — track model stats, suggest optimal models, consensus protocol"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class DisagreementVote(BaseModel):
    position: str  # the agent's stance
    confidence: float = 0.8  # 0-1


def register_model_performance_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Model Performance Learning ============

    @api_router.get("/workspaces/{workspace_id}/model-stats")
    async def get_model_stats(workspace_id: str, request: Request):
        """Get performance stats for all AI models in a workspace"""
        await _authed_user(request, workspace_id)
        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": "$agent",
                "total_messages": {"$sum": 1},
                "avg_response_ms": {"$avg": "$response_time_ms"},
                "total_tokens": {"$sum": {"$add": [{"$ifNull": ["$content_length", 0]}]}},
                "avg_code_quality": {"$avg": "$code_quality_score"},
                "code_blocks": {"$sum": "$code_blocks"},
            }},
            {"$sort": {"total_messages": -1}},
        ]
        stats = []
        async for doc in db.analytics.aggregate(pipeline):
            stats.append({
                "model": doc["_id"],
                "total_messages": doc["total_messages"],
                "avg_response_ms": round(doc.get("avg_response_ms") or 0),
                "total_tokens": doc.get("total_tokens", 0),
                "avg_code_quality": round(doc.get("avg_code_quality") or 0, 1),
                "code_blocks": doc.get("code_blocks", 0),
            })
        return {"stats": stats}

    @api_router.get("/workspaces/{workspace_id}/model-recommendations")
    async def get_model_recommendations(workspace_id: str, request: Request, task_type: str = "general"):
        """Suggest optimal model for a task type based on historical performance"""
        await _authed_user(request, workspace_id)

        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": "$agent",
                "count": {"$sum": 1},
                "avg_response_ms": {"$avg": "$response_time_ms"},
                "avg_quality": {"$avg": "$code_quality_score"},
                "code_blocks": {"$sum": "$code_blocks"},
            }},
        ]
        raw = []
        async for doc in db.analytics.aggregate(pipeline):
            raw.append(doc)

        recommendations = []
        for doc in raw:
            model = doc["_id"]
            score = 50  # base score
            avg_ms = doc.get("avg_response_ms") or 5000
            quality = doc.get("avg_quality") or 0
            code = doc.get("code_blocks") or 0
            count = doc.get("count") or 0

            # Speed bonus
            if avg_ms < 3000: score += 15
            elif avg_ms < 5000: score += 10
            elif avg_ms > 10000: score -= 10

            # Quality bonus
            score += min(quality * 5, 25)

            # Task-type adjustments
            if task_type == "code" and code > 0:
                score += 15
            elif task_type == "research" and count > 5:
                score += 10
            elif task_type == "creative":
                score += 5  # all models can be creative

            # Volume confidence
            if count >= 10: score += 5
            elif count < 3: score -= 10

            recommendations.append({
                "model": model,
                "score": max(0, min(100, round(score))),
                "avg_response_ms": round(avg_ms),
                "messages_analyzed": count,
                "strengths": _get_strengths(model, code, quality, avg_ms),
            })

        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return {"task_type": task_type, "recommendations": recommendations[:5]}

    def _get_strengths(model, code_blocks, quality, avg_ms):
        strengths = []
        if avg_ms < 3000: strengths.append("fast")
        if code_blocks > 5: strengths.append("strong at code")
        if quality > 6: strengths.append("high quality")
        model_traits = {
            "claude": ["reasoning", "analysis"], "chatgpt": ["versatile", "coding"],
            "gemini": ["research", "multimodal"], "deepseek": ["coding", "math"],
            "perplexity": ["research", "citations"], "mistral": ["efficient", "multilingual"],
            "grok": ["creative", "conversational"], "cohere": ["summarization"],
            "groq": ["ultra-fast", "inference"],
        }
        strengths.extend(model_traits.get(model, []))
        return strengths[:4]

    # ============ Auto-Routing ============

    @api_router.post("/workspaces/{workspace_id}/auto-route")
    async def auto_route_model(workspace_id: str, request: Request):
        """Automatically select the best AI model for a given task type based on performance history"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        task_type = body.get("task_type", "general")
        prompt_preview = body.get("prompt", "")

        # Auto-classify task type from prompt if not specified
        if task_type == "general" and prompt_preview:
            lower = prompt_preview.lower()
            if any(w in lower for w in ["code", "function", "debug", "implement", "refactor"]):
                task_type = "code"
            elif any(w in lower for w in ["research", "find", "search", "sources", "data"]):
                task_type = "research"
            elif any(w in lower for w in ["write", "draft", "blog", "article", "content"]):
                task_type = "writing"
            elif any(w in lower for w in ["analyze", "compare", "evaluate", "assess"]):
                task_type = "analysis"
            elif any(w in lower for w in ["summarize", "summary", "key points", "tldr"]):
                task_type = "summarization"
            elif any(w in lower for w in ["translate", "language", "spanish", "french"]):
                task_type = "translation"

        # Get performance data
        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": "$agent",
                "count": {"$sum": 1},
                "avg_ms": {"$avg": "$response_time_ms"},
                "avg_quality": {"$avg": "$code_quality_score"},
                "code_blocks": {"$sum": "$code_blocks"},
            }},
        ]
        raw = []
        async for doc in db.analytics.aggregate(pipeline):
            raw.append(doc)

        if not raw:
            # No data — return default recommendations
            defaults = {
                "code": "claude", "research": "perplexity", "writing": "chatgpt",
                "analysis": "claude", "summarization": "gemini", "translation": "mistral",
                "general": "chatgpt",
            }
            selected = defaults.get(task_type, "chatgpt")
            return {"selected_model": selected, "task_type": task_type, "confidence": 0.5, "reason": "Default recommendation (no performance data yet)", "data_points": 0}

        # Score models for this task type
        best_model = None
        best_score = -1
        for doc in raw:
            model = doc["_id"]
            score = 50
            avg_ms = doc.get("avg_ms") or 5000
            quality = doc.get("avg_quality") or 0
            code = doc.get("code_blocks") or 0
            count = doc.get("count") or 0

            if avg_ms < 3000: score += 15
            elif avg_ms < 5000: score += 10
            score += min(quality * 5, 25)
            if task_type == "code" and code > 0: score += 15
            elif task_type == "research" and count > 5: score += 10
            if count >= 10: score += 5
            elif count < 3: score -= 10

            if score > best_score:
                best_score = score
                best_model = model

        confidence = min(0.95, max(0.3, best_score / 100))
        total_data = sum(d.get("count", 0) for d in raw)

        return {
            "selected_model": best_model or "chatgpt",
            "task_type": task_type,
            "confidence": round(confidence, 2),
            "score": round(best_score),
            "reason": f"Best performer for '{task_type}' based on {total_data} interactions",
            "data_points": total_data,
        }

    # ============ Disagreement Resolution ============

    @api_router.post("/channels/{channel_id}/disagreements")
    async def create_disagreement(channel_id: str, request: Request):
        """Detect and create a disagreement resolution from recent messages"""
        user = await get_current_user(request)
        body = await request.json()
        topic = body.get("topic", "")
        if not topic:
            raise HTTPException(400, "Topic is required")

        dis_id = f"dis_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        disagreement = {
            "disagreement_id": dis_id,
            "channel_id": channel_id,
            "topic": topic,
            "status": "open",  # open, voting, resolved
            "votes": {},
            "resolution": None,
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.disagreements.insert_one(disagreement)
        return {k: v for k, v in disagreement.items() if k != "_id"}

    @api_router.post("/disagreements/{disagreement_id}/vote")
    async def submit_vote(disagreement_id: str, data: DisagreementVote, request: Request):
        """Submit a vote/position on a disagreement"""
        user = await get_current_user(request)
        body = await request.json()
        agent_key = body.get("agent_key", user["user_id"])

        dis = await db.disagreements.find_one({"disagreement_id": disagreement_id})
        if not dis:
            raise HTTPException(404, "Disagreement not found")
        if dis["status"] == "resolved":
            raise HTTPException(400, "Disagreement already resolved")

        await db.disagreements.update_one(
            {"disagreement_id": disagreement_id},
            {"$set": {
                f"votes.{agent_key}": {"position": data.position, "confidence": data.confidence, "voted_at": datetime.now(timezone.utc).isoformat()},
                "status": "voting",
            }}
        )
        return await db.disagreements.find_one({"disagreement_id": disagreement_id}, {"_id": 0})

    @api_router.post("/disagreements/{disagreement_id}/resolve")
    async def resolve_disagreement(disagreement_id: str, request: Request):
        """Resolve a disagreement — picks highest-confidence majority position"""
        await get_current_user(request)
        dis = await db.disagreements.find_one({"disagreement_id": disagreement_id}, {"_id": 0})
        if not dis:
            raise HTTPException(404, "Disagreement not found")

        votes = dis.get("votes") or {}
        if len(votes) < 2:
            raise HTTPException(400, "Need at least 2 votes to resolve")

        # Weighted voting: position with highest total confidence wins
        position_scores = {}
        for agent, vote in votes.items():
            pos = vote["position"]
            conf = vote.get("confidence", 0.5)
            position_scores[pos] = position_scores.get(pos, 0) + conf

        winner = max(position_scores, key=position_scores.get)
        total_votes = len(votes)
        winner_votes = sum(1 for v in votes.values() if v["position"] == winner)

        resolution = {
            "winning_position": winner,
            "confidence_score": round(position_scores[winner] / sum(position_scores.values()), 2),
            "vote_count": total_votes,
            "winner_votes": winner_votes,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.disagreements.update_one(
            {"disagreement_id": disagreement_id},
            {"$set": {"status": "resolved", "resolution": resolution}}
        )
        return {"disagreement_id": disagreement_id, "resolution": resolution}

    @api_router.get("/channels/{channel_id}/disagreements")
    async def list_disagreements(channel_id: str, request: Request):
        await get_current_user(request)
        items = await db.disagreements.find({"channel_id": channel_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return items

    # ============ Workspace Disagreement Audit Log ============

    @api_router.get("/workspaces/{ws_id}/disagreement-audit")
    async def workspace_disagreement_audit(ws_id: str, request: Request, status: str = None, limit: int = 50):
        """Full audit log of all disagreements across a workspace with resolution details."""
        await get_current_user(request)
        query = {"workspace_id": ws_id}
        if status:
            query["status"] = status
        
        items = await db.disagreements.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Enrich with channel names
        channel_ids = list(set(d.get("channel_id", "") for d in items))
        channels = {}
        if channel_ids:
            ch_docs = await db.channels.find({"channel_id": {"$in": channel_ids}}, {"_id": 0, "channel_id": 1, "name": 1}).to_list(50)
            channels = {c["channel_id"]: c.get("name", "") for c in ch_docs}
        
        for item in items:
            item["channel_name"] = channels.get(item.get("channel_id", ""), "")
        
        # Summary stats
        total = len(items)
        resolved = sum(1 for d in items if d.get("status") == "resolved")
        open_count = sum(1 for d in items if d.get("status") in ("detected", "open", "voting"))
        
        return {
            "items": items,
            "stats": {
                "total": total,
                "resolved": resolved,
                "open": open_count,
                "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0,
            },
        }

    @api_router.post("/disagreements/{disagreement_id}/manual-resolve")
    async def manual_resolve_disagreement(disagreement_id: str, request: Request):
        """Manually resolve a disagreement with a human decision."""
        user = await get_current_user(request)
        body = await request.json()
        
        dis = await db.disagreements.find_one({"disagreement_id": disagreement_id}, {"_id": 0})
        if not dis:
            raise HTTPException(404, "Disagreement not found")
        
        resolution = {
            "winning_position": body.get("resolution", ""),
            "resolved_by": user["user_id"],
            "resolution_type": "manual",
            "resolution_notes": body.get("notes", ""),
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
        
        await db.disagreements.update_one(
            {"disagreement_id": disagreement_id},
            {"$set": {"status": "resolved", "resolution": resolution}}
        )
        return {"disagreement_id": disagreement_id, "resolution": resolution}

    # ============ Human Checkpoint Configuration (#5) ============

    CHECKPOINT_TYPES = ["approve_reject", "review_edit", "select_option", "provide_input", "confirm_proceed"]

    @api_router.post("/workflows/{workflow_id}/checkpoints")
    async def add_checkpoint(workflow_id: str, request: Request):
        """Add a human checkpoint to a workflow at a specific position"""
        await get_current_user(request)
        body = await request.json()
        after_node_id = body.get("after_node_id")
        label = body.get("label", "Human Checkpoint")
        instructions = body.get("instructions", "Review and approve before continuing.")
        checkpoint_type = body.get("checkpoint_type", "approve_reject")
        if checkpoint_type not in CHECKPOINT_TYPES:
            checkpoint_type = "approve_reject"
        timeout_minutes = body.get("timeout_minutes")
        auto_approve_if = body.get("auto_approve_if")

        wf = await db.workflows.find_one({"workflow_id": workflow_id})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        node_id = f"wn_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        node = {
            "node_id": node_id, "workflow_id": workflow_id, "type": "human_review",
            "label": label, "system_prompt": instructions,
            "checkpoint_type": checkpoint_type,
            "timeout_minutes": timeout_minutes,
            "auto_approve_if": auto_approve_if,
            "position_x": 0, "position_y": 0,
            "position": 0, "created_at": now,
        }
        await db.workflow_nodes.insert_one(node)

        if after_node_id:
            downstream = await db.workflow_edges.find(
                {"workflow_id": workflow_id, "source_node_id": after_node_id}, {"_id": 0}
            ).to_list(10)
            for edge in downstream:
                await db.workflow_edges.update_one(
                    {"edge_id": edge["edge_id"]},
                    {"$set": {"source_node_id": node_id}}
                )
            await db.workflow_edges.insert_one({
                "edge_id": f"we_{uuid.uuid4().hex[:12]}", "workflow_id": workflow_id,
                "source_node_id": after_node_id, "target_node_id": node_id,
                "edge_type": "default", "created_at": now,
            })

        return {k: v for k, v in node.items() if k != "_id"}

    @api_router.get("/workflows/{workflow_id}/checkpoints")
    async def list_checkpoints(workflow_id: str, request: Request):
        """List all human checkpoints in a workflow"""
        await get_current_user(request)
        nodes = await db.workflow_nodes.find(
            {"workflow_id": workflow_id, "type": "human_review"}, {"_id": 0}
        ).to_list(20)
        return nodes

    @api_router.get("/checkpoints/types")
    async def get_checkpoint_types(request: Request):
        """Get available checkpoint types"""
        await get_current_user(request)
        return {"types": [
            {"key": "approve_reject", "name": "Approve / Reject", "description": "Simple gate — reviewer approves or rejects"},
            {"key": "review_edit", "name": "Review & Edit", "description": "Reviewer can modify output before it passes downstream"},
            {"key": "select_option", "name": "Select Option", "description": "Reviewer picks from multiple options produced by a node"},
            {"key": "provide_input", "name": "Provide Input", "description": "Pauses to ask reviewer for additional information"},
            {"key": "confirm_proceed", "name": "Confirm & Proceed", "description": "Low-friction: shows summary, asks Continue?"},
        ]}
