from nexus_utils import now_iso
"""Agent-to-Agent Protocol — Structured inter-agent communication.

Enables agents to send direct requests to specific other agents with
structured payloads, priority levels, and tracked response times.
Prevents chaos of unstructured @mentions by enforcing request/response pattern.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



def register_agent_protocol_routes(api_router, db, get_current_user):

    @api_router.post("/channels/{ch_id}/agent-request")
    async def create_agent_request(ch_id: str, request: Request):
        """One agent sends a structured request to another agent."""
        user = await get_current_user(request)
        body = await request.json()
        
        req_id = f"areq_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        
        agent_request = {
            "request_id": req_id,
            "channel_id": ch_id,
            "from_agent": body.get("from_agent", ""),
            "to_agent": body.get("to_agent", ""),
            "request_type": body.get("request_type", "review"),
            "subject": body.get("subject", ""),
            "payload": body.get("payload", ""),
            "priority": body.get("priority", "normal"),
            "status": "pending",
            "response": None,
            "response_at": None,
            "created_at": now,
            "timeout_minutes": body.get("timeout_minutes", 5),
        }
        await db.agent_requests.insert_one(agent_request)
        agent_request.pop("_id", None)
        
        # Post notification in channel
        await db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": ch_id,
            "sender_type": "system",
            "sender_id": "protocol",
            "sender_name": "Agent Protocol",
            "content": f"**Agent Request** [{agent_request['priority'].upper()}]\n"
                       f"From: {agent_request['from_agent']} -> To: {agent_request['to_agent']}\n"
                       f"Type: {agent_request['request_type']}\n"
                       f"Subject: {agent_request['subject']}\n"
                       f"---\n{agent_request['payload'][:500]}",
            "created_at": now,
        })
        
        return agent_request

    @api_router.post("/agent-requests/{req_id}/respond")
    async def respond_to_request(req_id: str, request: Request):
        """Target agent responds to a request."""
        user = await get_current_user(request)
        body = await request.json()
        
        ar = await db.agent_requests.find_one({"request_id": req_id}, {"_id": 0})
        if not ar:
            raise HTTPException(404, "Request not found")
        if ar["status"] != "pending":
            raise HTTPException(400, f"Request already {ar['status']}")
        
        await db.agent_requests.update_one(
            {"request_id": req_id},
            {"$set": {
                "status": "completed",
                "response": body.get("response", ""),
                "response_at": now_iso(),
            }}
        )
        
        # Post response in channel
        await db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": ar["channel_id"],
            "sender_type": "system",
            "sender_id": "protocol",
            "sender_name": "Agent Protocol",
            "content": f"**Agent Response** to request {req_id}\n"
                       f"From: {ar['to_agent']} -> {ar['from_agent']}\n"
                       f"---\n{body.get('response', '')[:500]}",
            "created_at": now_iso(),
        })
        
        return {"request_id": req_id, "status": "completed"}

    @api_router.get("/channels/{ch_id}/agent-requests")
    async def list_agent_requests(ch_id: str, request: Request, status: str = None):
        user = await get_current_user(request)
        query = {"channel_id": ch_id}
        if status:
            query["status"] = status
        reqs = await db.agent_requests.find(query, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
        return reqs

    @api_router.get("/channels/{ch_id}/agent-requests/pending/{agent_key}")
    async def get_pending_for_agent(ch_id: str, agent_key: str, request: Request):
        """Get pending requests assigned to a specific agent."""
        user = await get_current_user(request)
        reqs = await db.agent_requests.find(
            {"channel_id": ch_id, "to_agent": agent_key, "status": "pending"},
            {"_id": 0}
        ).sort("created_at", 1).to_list(10)
        return reqs
