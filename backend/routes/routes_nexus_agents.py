"""Nexus Agent routes - custom workspace-specific AI agents"""
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List

# Plan limits for custom agents
AGENT_LIMITS = {
    "free": 3,
    "pro": 10,
    "enterprise": 100,
}

# Available colors for agent avatars
AGENT_COLORS = [
    "#E11D48", "#DB2777", "#C026D3", "#9333EA", "#7C3AED",
    "#6366F1", "#3B82F6", "#0EA5E9", "#06B6D4", "#14B8A6",
    "#10B981", "#22C55E", "#84CC16", "#EAB308", "#F59E0B",
    "#F97316", "#EF4444", "#78716C", "#64748B", "#6B7280",
]


class CreateNexusAgent(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    base_model: str  # claude, chatgpt, deepseek, etc.
    system_prompt: str = Field(..., min_length=10, max_length=2000)
    color: Optional[str] = None


class UpdateNexusAgent(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    base_model: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=10, max_length=2000)
    color: Optional[str] = None


def register_nexus_agent_routes(api_router, db, get_current_user, AI_MODELS):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    
    @api_router.get("/workspaces/{workspace_id}/agents")
    async def get_workspace_agents(workspace_id: str, request: Request):
        """Get all custom Nexus Agents for a workspace"""
        user = await _authed_user(request, workspace_id)
        
        # Verify workspace access
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        agents = await db.nexus_agents.find(
            {"workspace_id": workspace_id},
            {"_id": 0}
        ).to_list(100)
        
        # Get plan limit
        plan = user.get("plan", "free")
        limit = AGENT_LIMITS.get(plan, 3)
        
        return {
            "agents": agents,
            "count": len(agents),
            "limit": limit,
            "plan": plan
        }
    
    @api_router.post("/workspaces/{workspace_id}/agents")
    async def create_nexus_agent(workspace_id: str, data: CreateNexusAgent, request: Request):
        """Create a new custom Nexus Agent"""
        user = await _authed_user(request, workspace_id)
        
        # Verify workspace access
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        # Check plan limit
        plan = user.get("plan", "free")
        limit = AGENT_LIMITS.get(plan, 3)
        current_count = await db.nexus_agents.count_documents({"workspace_id": workspace_id})
        
        if current_count >= limit:
            raise HTTPException(403, f"Agent limit reached ({limit} for {plan} plan). Upgrade to create more agents.")
        
        # Validate base model
        if data.base_model not in AI_MODELS:
            raise HTTPException(400, f"Invalid base model. Choose from: {', '.join(AI_MODELS.keys())}")
        
        # Generate agent ID and set defaults
        agent_id = f"nxa_{uuid.uuid4().hex[:12]}"
        color = data.color if data.color in AGENT_COLORS else AGENT_COLORS[current_count % len(AGENT_COLORS)]
        
        agent = {
            "agent_id": agent_id,
            "workspace_id": workspace_id,
            "created_by": user["user_id"],
            "name": data.name,
            "description": data.description or "",
            "base_model": data.base_model,
            "system_prompt": data.system_prompt,
            "color": color,
            "avatar": data.name[:2].upper(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        await db.nexus_agents.insert_one(agent)
        
        # Return without _id
        agent.pop("_id", None)
        return agent
    
    @api_router.get("/workspaces/{workspace_id}/agents/{agent_id}")
    async def get_nexus_agent(workspace_id: str, agent_id: str, request: Request):
        """Get a specific Nexus Agent"""
        await _authed_user(request, workspace_id)
        
        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": workspace_id},
            {"_id": 0}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")
        
        return agent
    
    @api_router.put("/workspaces/{workspace_id}/agents/{agent_id}")
    async def update_nexus_agent(workspace_id: str, agent_id: str, data: UpdateNexusAgent, request: Request):
        """Update a Nexus Agent"""
        await _authed_user(request, workspace_id)
        
        agent = await db.nexus_agents.find_one({"agent_id": agent_id, "workspace_id": workspace_id})
        if not agent:
            raise HTTPException(404, "Agent not found")
        
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if data.name is not None:
            updates["name"] = data.name
            updates["avatar"] = data.name[:2].upper()
        if data.description is not None:
            updates["description"] = data.description
        if data.base_model is not None:
            if data.base_model not in AI_MODELS:
                raise HTTPException(400, f"Invalid base model")
            updates["base_model"] = data.base_model
        if data.system_prompt is not None:
            updates["system_prompt"] = data.system_prompt
        if data.color is not None and data.color in AGENT_COLORS:
            updates["color"] = data.color
        
        await db.nexus_agents.update_one(
            {"agent_id": agent_id},
            {"$set": updates}
        )
        
        updated = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0})
        return updated
    
    @api_router.delete("/workspaces/{workspace_id}/agents/{agent_id}")
    async def delete_nexus_agent(workspace_id: str, agent_id: str, request: Request):
        """Delete a Nexus Agent"""
        await _authed_user(request, workspace_id)
        
        result = await db.nexus_agents.delete_one({"agent_id": agent_id, "workspace_id": workspace_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Agent not found")
        
        return {"message": "Agent deleted"}
    
    @api_router.get("/workspaces/{workspace_id}/available-models")
    async def get_available_models(workspace_id: str, request: Request):
        """Get list of available base models for creating Nexus Agents"""
        await _authed_user(request, workspace_id)
        
        models = []
        for key, config in AI_MODELS.items():
            models.append({
                "key": key,
                "name": config["name"],
                "color": config["color"],
                "requires_user_key": config.get("requires_user_key", False),
            })
        
        return {"models": models}
