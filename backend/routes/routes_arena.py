from nexus_utils import now_iso
"""Agent Arena — Side-by-side model evaluation with voting and leaderboards.

Send the same prompt to multiple AI models simultaneously, display responses
side-by-side, and let users vote on which is best. Tracks win rates over time.
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



def register_arena_routes(api_router, db, get_current_user):

    @api_router.post("/workspaces/{ws_id}/arena/battle")
    async def create_battle(ws_id: str, request: Request):
        """Send same prompt to multiple models and get side-by-side responses."""
        user = await get_current_user(request)
        body = await request.json()
        prompt = body.get("prompt", "").strip()
        models = body.get("models", ["chatgpt", "claude"])
        category = body.get("category", "general")
        
        if not prompt:
            raise HTTPException(400, "Prompt required")
        if len(models) < 2 or len(models) > 4:
            raise HTTPException(400, "Select 2-4 models")
        
        battle_id = f"battle_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        
        battle = {
            "battle_id": battle_id,
            "workspace_id": ws_id,
            "prompt": prompt,
            "category": category,
            "models": models,
            "responses": {},
            "votes": {},
            "winner": None,
            "status": "running",
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.arena_battles.insert_one(battle)
        battle.pop("_id", None)
        
        # Run all models in parallel
        asyncio.create_task(_run_battle(db, battle, user["user_id"], ws_id))
        
        return battle

    @api_router.get("/workspaces/{ws_id}/arena/battles")
    async def list_battles(ws_id: str, request: Request, limit: int = 20):
        user = await get_current_user(request)
        battles = await db.arena_battles.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return battles

    @api_router.get("/arena/battles/{battle_id}")
    async def get_battle(battle_id: str, request: Request):
        user = await get_current_user(request)
        battle = await db.arena_battles.find_one({"battle_id": battle_id}, {"_id": 0})
        if not battle:
            raise HTTPException(404, "Battle not found")
        return battle

    @api_router.post("/arena/battles/{battle_id}/vote")
    async def vote_battle(battle_id: str, request: Request):
        """Vote for the best response in a battle."""
        user = await get_current_user(request)
        body = await request.json()
        winner_model = body.get("winner", "")
        
        battle = await db.arena_battles.find_one({"battle_id": battle_id}, {"_id": 0})
        if not battle:
            raise HTTPException(404, "Battle not found")
        
        # Record vote
        await db.arena_battles.update_one(
            {"battle_id": battle_id},
            {"$set": {
                f"votes.{user['user_id']}": winner_model,
                "winner": winner_model,
            }}
        )
        
        # Update model leaderboard
        await db.arena_leaderboard.update_one(
            {"model": winner_model, "workspace_id": battle["workspace_id"], "category": battle.get("category", "general")},
            {"$inc": {"wins": 1, "total_battles": 0}, "$set": {"last_win_at": now_iso()}},
            upsert=True,
        )
        # Increment total_battles for all participating models
        for m in battle.get("models") or []:
            await db.arena_leaderboard.update_one(
                {"model": m, "workspace_id": battle["workspace_id"], "category": battle.get("category", "general")},
                {"$inc": {"total_battles": 1}, "$setOnInsert": {"wins": 0, "last_win_at": None}},
                upsert=True,
            )
        
        return {"voted": winner_model, "battle_id": battle_id}

    @api_router.get("/workspaces/{ws_id}/arena/leaderboard")
    async def get_leaderboard(ws_id: str, request: Request, category: str = None):
        """Model leaderboard with win rates."""
        user = await get_current_user(request)
        query = {"workspace_id": ws_id}
        if category:
            query["category"] = category
        
        entries = await db.arena_leaderboard.find(query, {"_id": 0}).to_list(50)
        
        # Calculate win rates
        for e in entries:
            total = e.get("total_battles", 0)
            wins = e.get("wins", 0)
            e["win_rate"] = round(wins / total * 100, 1) if total > 0 else 0
        
        entries.sort(key=lambda x: x.get("win_rate", 0), reverse=True)
        return {"leaderboard": entries}


async def _run_battle(db, battle, user_id, ws_id):
    """Run all models in parallel for a battle."""
    from ai_providers import call_ai_direct
    from collaboration_core import get_ai_key_for_agent
    
    import time
    responses = {}
    
    async def call_model(model_key):
        try:
            api_key, _ = await get_ai_key_for_agent(user_id, ws_id, model_key)
            if not api_key:
                return model_key, {"error": "No API key", "text": "", "time_ms": 0, "tokens": 0}
            
            start = time.time()
            text = await call_ai_direct(model_key, api_key, "You are a helpful assistant.", battle["prompt"], workspace_id=ws_id, db=db)
            duration = int((time.time() - start) * 1000)
            tokens = max(1, len(text) // 4)
            
            return model_key, {"text": text[:3000], "time_ms": duration, "tokens": tokens, "error": None}
        except Exception as e:
            return model_key, {"error": str(e)[:200], "text": "", "time_ms": 0, "tokens": 0}
    
    tasks = [call_model(m) for m in battle["models"]]
    results = await asyncio.gather(*tasks)
    
    for model_key, result in results:
        responses[model_key] = result
    
    await db.arena_battles.update_one(
        {"battle_id": battle["battle_id"]},
        {"$set": {"responses": responses, "status": "completed"}}
    )
