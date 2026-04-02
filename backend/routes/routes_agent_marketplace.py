"""AI Agent Marketplace — Discover, rate, share, and install custom AI agent configurations."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

MARKETPLACE_CATEGORIES = ["coding", "research", "creative", "business", "productivity", "data", "custom"]


class AgentPublish(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=2000)
    category: str = "custom"
    base_model: str = "claude"
    system_prompt: str = Field(..., min_length=10, max_length=10000)
    tags: List[str] = []
    icon: str = ""
    color: str = "#6366f1"


class AgentRate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: str = Field("", max_length=500)


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    tags: Optional[List[str]] = None
    icon: Optional[str] = None
    color: Optional[str] = None


from nexus_utils import safe_regex

def register_agent_marketplace_routes(api_router, db, get_current_user):

    @api_router.get("/marketplace/agents")
    async def browse_agents(
        request: Request,
        category: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "popular",
        limit: int = 24,
        skip: int = 0,
    ):
        """Browse published agent configurations."""
        query = {"status": "published"}
        if category and category in MARKETPLACE_CATEGORIES:
            query["category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": safe_regex(search), "$options": "i"}},
                {"description": {"$regex": safe_regex(search), "$options": "i"}},
                {"tags": {"$regex": safe_regex(search), "$options": "i"}},
            ]

        sort_key = {"popular": [("installs", -1)], "top_rated": [("avg_rating", -1)], "newest": [("created_at", -1)], "name": [("name", 1)]}
        sort_spec = sort_key.get(sort, [("installs", -1)])

        agents = await db.agent_marketplace.find(query, {"_id": 0, "system_prompt": 0}).sort(sort_spec).skip(skip).limit(min(limit, 50)).to_list(50)
        total = await db.agent_marketplace.count_documents(query)

        return {"agents": agents, "total": total, "categories": MARKETPLACE_CATEGORIES}

    @api_router.get("/marketplace/agents/{agent_id}")
    async def get_agent_detail(agent_id: str, request: Request):
        """Get agent details. System prompt hidden unless requester is the creator."""
        agent = await db.agent_marketplace.find_one({"agent_id": agent_id, "status": "published"}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        # S-03: Hide system prompt from non-creators
        try:
            user = await get_current_user(request)
            if agent.get("publisher_id") != user.get("user_id"):
                agent["system_prompt"] = "[Hidden — install to use this agent]"
        except Exception:
            agent["system_prompt"] = "[Hidden — install to use this agent]"
        return agent

    @api_router.post("/marketplace/agents")
    async def publish_agent(data: AgentPublish, request: Request):
        """Publish a custom agent configuration to the marketplace."""
        user = await get_current_user(request)
        if data.category not in MARKETPLACE_CATEGORIES:
            raise HTTPException(400, f"Category must be one of: {', '.join(MARKETPLACE_CATEGORIES)}")

        agent_id = f"mkt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        agent = {
            "agent_id": agent_id,
            "name": data.name,
            "description": data.description,
            "category": data.category,
            "base_model": data.base_model,
            "system_prompt": data.system_prompt,
            "tags": data.tags[:10],
            "icon": data.icon or data.name[0].upper(),
            "color": data.color,
            "creator_id": user["user_id"],
            "creator_name": user.get("name", "Anonymous"),
            "status": "published",
            "installs": 0,
            "avg_rating": 0,
            "rating_count": 0,
            "ratings": [],
            "created_at": now,
            "updated_at": now,
        }
        await db.agent_marketplace.insert_one(agent)
        agent.pop("_id", None)
        return agent

    @api_router.put("/marketplace/agents/{agent_id}")
    async def update_agent(agent_id: str, data: AgentUpdate, request: Request):
        """Update a published agent (creator only)."""
        user = await get_current_user(request)
        agent = await db.agent_marketplace.find_one({"agent_id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        if agent["creator_id"] != user["user_id"] and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Only the creator can update this agent")

        updates = {k: v for k, v in data.dict().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        if "category" in updates and updates["category"] not in MARKETPLACE_CATEGORIES:
            raise HTTPException(400, f"Invalid category")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.agent_marketplace.update_one({"agent_id": agent_id}, {"$set": updates})
        return {"status": "updated", "agent_id": agent_id}

    @api_router.delete("/marketplace/agents/{agent_id}")
    async def delete_agent(agent_id: str, request: Request):
        """Delete a published agent (creator or admin)."""
        user = await get_current_user(request)
        agent = await db.agent_marketplace.find_one({"agent_id": agent_id}, {"_id": 0, "creator_id": 1})
        if not agent:
            raise HTTPException(404, "Agent not found")
        if agent["creator_id"] != user["user_id"] and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Only the creator or admin can delete this agent")
        await db.agent_marketplace.delete_one({"agent_id": agent_id})
        return {"status": "deleted"}

    @api_router.post("/marketplace/agents/{agent_id}/rate")
    async def rate_agent(agent_id: str, data: AgentRate, request: Request):
        """Rate an agent configuration."""
        user = await get_current_user(request)
        agent = await db.agent_marketplace.find_one({"agent_id": agent_id, "status": "published"}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")

        existing = [r for r in agent.get("ratings") or [] if r.get("user_id") == user["user_id"]]
        now = datetime.now(timezone.utc).isoformat()
        new_rating = {
            "user_id": user["user_id"],
            "user_name": user.get("name", "Anonymous"),
            "rating": data.rating,
            "review": data.review,
            "created_at": now,
        }

        if existing:
            await db.agent_marketplace.update_one(
                {"agent_id": agent_id, "ratings.user_id": user["user_id"]},
                {"$set": {"ratings.$": new_rating}}
            )
        else:
            await db.agent_marketplace.update_one(
                {"agent_id": agent_id},
                {"$push": {"ratings": new_rating}, "$inc": {"rating_count": 1}}
            )

        updated = await db.agent_marketplace.find_one({"agent_id": agent_id}, {"_id": 0, "ratings": 1})
        ratings = updated.get("ratings") or []
        avg = round(sum(r["rating"] for r in ratings) / len(ratings), 1) if ratings else 0
        await db.agent_marketplace.update_one({"agent_id": agent_id}, {"$set": {"avg_rating": avg, "rating_count": len(ratings)}})

        return {"status": "rated", "avg_rating": avg, "rating_count": len(ratings)}

    @api_router.post("/marketplace/agents/{agent_id}/install")
    async def install_agent(agent_id: str, request: Request):
        """Install a marketplace agent to user's workspace."""
        user = await get_current_user(request)
        workspace_id = request.query_params.get("workspace_id")
        if not workspace_id:
            raise HTTPException(400, "workspace_id required")

        agent = await db.agent_marketplace.find_one({"agent_id": agent_id, "status": "published"}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")

        install_id = f"inst_{uuid.uuid4().hex[:12]}"
        await db.agent_installs.insert_one({
            "install_id": install_id,
            "agent_id": agent_id,
            "workspace_id": workspace_id,
            "user_id": user["user_id"],
            "agent_name": agent["name"],
            "base_model": agent["base_model"],
            "system_prompt": agent["system_prompt"],
            "installed_at": datetime.now(timezone.utc).isoformat(),
        })

        await db.agent_marketplace.update_one({"agent_id": agent_id}, {"$inc": {"installs": 1}})
        return {"status": "installed", "install_id": install_id}

    @api_router.get("/marketplace/my-agents")
    async def my_published_agents(request: Request):
        """List agents published by the current user."""
        user = await get_current_user(request)
        agents = await db.agent_marketplace.find(
            {"creator_id": user["user_id"]}, {"_id": 0, "system_prompt": 0, "ratings": 0}
        ).sort("created_at", -1).to_list(50)
        return {"agents": agents}

    @api_router.get("/marketplace/installed")
    async def installed_agents(request: Request):
        """List agents installed in a workspace."""
        user = await get_current_user(request)
        workspace_id = request.query_params.get("workspace_id")
        if not workspace_id:
            raise HTTPException(400, "workspace_id required")
        installs = await db.agent_installs.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("installed_at", -1).to_list(50)
        return {"installs": installs}

    @api_router.get("/marketplace/agent-stats")
    async def marketplace_stats():
        """Public marketplace statistics."""
        total = await db.agent_marketplace.count_documents({"status": "published"})
        total_installs = 0
        pipeline = [{"$match": {"status": "published"}}, {"$group": {"_id": None, "total": {"$sum": "$installs"}}}]
        async for doc in db.agent_marketplace.aggregate(pipeline):
            total_installs = doc.get("total", 0)

        cat_counts = {}
        for cat in MARKETPLACE_CATEGORIES:
            cat_counts[cat] = await db.agent_marketplace.count_documents({"status": "published", "category": cat})

        return {"total_agents": total, "total_installs": total_installs, "categories": cat_counts}
