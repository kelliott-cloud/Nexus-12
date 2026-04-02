"""Support Desk — lightweight JSD (Jira Service Desk) for internal/external ticket management"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)

VALID_TICKET_STATUSES = ["open", "in_progress", "waiting_on_customer", "waiting_on_support", "resolved", "closed"]
VALID_TICKET_PRIORITIES = ["low", "medium", "high", "urgent"]
VALID_TICKET_TYPES = ["bug", "enhancement", "question", "billing", "general_support", "incident", "feature_request", "access_request"]
VALID_SLA_POLICIES = ["standard", "priority", "enterprise"]

SLA_TARGETS = {
    "standard": {"first_response_hours": 24, "resolution_hours": 72},
    "priority": {"first_response_hours": 4, "resolution_hours": 24},
    "enterprise": {"first_response_hours": 1, "resolution_hours": 8},
}


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    ticket_type: str = "question"
    priority: str = "medium"
    category: str = ""

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    category: Optional[str] = None

class TicketReply(BaseModel):
    content: str = Field(..., min_length=1)
    is_internal: bool = False  # Internal notes vs customer-visible replies



def register_support_desk_routes(api_router, db, get_current_user):

    # ============ Tickets CRUD ============

    @api_router.post("/support/tickets")
    async def create_ticket(data: TicketCreate, request: Request):
        """Create a support ticket"""
        user = await get_current_user(request)
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        ticket = {
            "ticket_id": ticket_id,
            "subject": data.subject,
            "description": data.description,
            "ticket_type": data.ticket_type if data.ticket_type in VALID_TICKET_TYPES else "question",
            "priority": data.priority if data.priority in VALID_TICKET_PRIORITIES else "medium",
            "status": "open",
            "category": data.category,
            "org_id": user.get("org_id"),
            "requester_id": user["user_id"],
            "requester_name": user.get("name", ""),
            "requester_email": user.get("email", ""),
            "assigned_to": None,
            "assigned_name": None,
            "sla_policy": "standard",
            "first_response_at": None,
            "resolved_at": None,
            "sla_first_response_breached": False,
            "sla_resolution_breached": False,
            "reply_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        await db.support_tickets.insert_one(ticket)

        # Log activity
        await db.ticket_activity.insert_one({
            "activity_id": f"tka_{uuid.uuid4().hex[:8]}",
            "ticket_id": ticket_id, "action": "created",
            "actor_id": user["user_id"], "actor_name": user.get("name", ""),
            "timestamp": now,
        })

        return {k: v for k, v in ticket.items() if k != "_id"}

    @api_router.get("/support/tickets")
    async def list_tickets(request: Request, status: Optional[str] = None, priority: Optional[str] = None, assigned_to: Optional[str] = None, requester_id: Optional[str] = None, org_id: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0):
        """List support tickets with filters — org_id scopes results for Org Admins"""
        user = await get_current_user(request)
        query = {}

        if org_id:
            query["org_id"] = org_id
        elif user.get("role") != "super_admin":
            user_orgs = await db.org_memberships.find(
                {"user_id": user["user_id"]}, {"_id": 0, "org_id": 1}
            ).to_list(100)
            org_ids = [m["org_id"] for m in user_orgs]
            if org_ids:
                query["$or"] = [
                    {"requester_id": user["user_id"]},
                    {"org_id": {"$in": org_ids}},
                    {"org_id": {"$exists": False}},
                ]

        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if assigned_to:
            query["assigned_to"] = assigned_to
        if requester_id:
            query["requester_id"] = requester_id
        if search:
            from nexus_utils import safe_regex
            search_filter = [{"subject": {"$regex": safe_regex(search), "$options": "i"}}, {"description": {"$regex": safe_regex(search), "$options": "i"}}]
            if "$or" in query:
                query["$and"] = [{"$or": query.pop("$or")}, {"$or": search_filter}]
            else:
                query["$or"] = search_filter

        tickets = await db.support_tickets.find(query, {"_id": 0}).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.support_tickets.count_documents(query)
        return {"tickets": tickets, "total": total}

    @api_router.get("/support/tickets/my")
    async def my_tickets(request: Request):
        """Get tickets submitted by current user"""
        user = await get_current_user(request)
        tickets = await db.support_tickets.find({"requester_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(50)
        return {"tickets": tickets}

    @api_router.get("/support/tickets/assigned")
    async def assigned_tickets(request: Request):
        """Get tickets assigned to current user (agent view)"""
        user = await get_current_user(request)
        tickets = await db.support_tickets.find({"assigned_to": user["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(50)
        return {"tickets": tickets}

    @api_router.get("/support/tickets/{ticket_id}")
    async def get_ticket(ticket_id: str, request: Request):
        await get_current_user(request)
        ticket = await db.support_tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        return ticket

    @api_router.put("/support/tickets/{ticket_id}")
    async def update_ticket(ticket_id: str, data: TicketUpdate, request: Request):
        user = await get_current_user(request)
        ticket = await db.support_tickets.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(404, "Ticket not found")

        updates = {"updated_at": now_iso()}
        changes = []

        if data.status is not None and data.status in VALID_TICKET_STATUSES:
            old = ticket.get("status")
            updates["status"] = data.status
            changes.append(f"status: {old} → {data.status}")
            if data.status == "resolved" and not ticket.get("resolved_at"):
                updates["resolved_at"] = now_iso()
                # Check SLA breach
                sla = SLA_TARGETS.get(ticket.get("sla_policy", "standard"), SLA_TARGETS["standard"])
                created = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - created).total_seconds() / 3600
                if elapsed > sla["resolution_hours"]:
                    updates["sla_resolution_breached"] = True

        if data.priority is not None and data.priority in VALID_TICKET_PRIORITIES:
            updates["priority"] = data.priority
            changes.append(f"priority: {ticket.get('priority')} → {data.priority}")

        if data.assigned_to is not None:
            updates["assigned_to"] = data.assigned_to
            # Look up assignee name
            assignee = await db.users.find_one({"user_id": data.assigned_to}, {"_id": 0, "name": 1})
            updates["assigned_name"] = assignee["name"] if assignee else data.assigned_to
            changes.append(f"assigned to {updates['assigned_name']}")

        if data.category is not None:
            updates["category"] = data.category

        await db.support_tickets.update_one({"ticket_id": ticket_id}, {"$set": updates})

        if changes:
            await db.ticket_activity.insert_one({
                "activity_id": f"tka_{uuid.uuid4().hex[:8]}",
                "ticket_id": ticket_id, "action": "updated",
                "actor_id": user["user_id"], "actor_name": user.get("name", ""),
                "details": {"changes": changes},
                "timestamp": now_iso(),
            })

        return await db.support_tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})

    # ============ Ticket Replies ============

    @api_router.post("/support/tickets/{ticket_id}/replies")
    async def add_reply(ticket_id: str, data: TicketReply, request: Request):
        user = await get_current_user(request)
        ticket = await db.support_tickets.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(404, "Ticket not found")

        reply_id = f"tr_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        reply = {
            "reply_id": reply_id, "ticket_id": ticket_id,
            "content": data.content, "is_internal": data.is_internal,
            "author_id": user["user_id"], "author_name": user.get("name", ""),
            "created_at": now,
        }
        await db.ticket_replies.insert_one(reply)

        # Update ticket
        updates = {"updated_at": now, "reply_count": ticket.get("reply_count", 0) + 1}

        # First response SLA
        if not ticket.get("first_response_at") and user["user_id"] != ticket["requester_id"]:
            updates["first_response_at"] = now
            sla = SLA_TARGETS.get(ticket.get("sla_policy", "standard"), SLA_TARGETS["standard"])
            created = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            if elapsed > sla["first_response_hours"]:
                updates["sla_first_response_breached"] = True

        # Auto-update status based on who replied
        if user["user_id"] == ticket["requester_id"]:
            if ticket.get("status") == "waiting_on_customer":
                updates["status"] = "waiting_on_support"
        else:
            if ticket.get("status") == "open":
                updates["status"] = "in_progress"

        await db.support_tickets.update_one({"ticket_id": ticket_id}, {"$set": updates})

        return {k: v for k, v in reply.items() if k != "_id"}

    @api_router.get("/support/tickets/{ticket_id}/replies")
    async def list_replies(ticket_id: str, request: Request, include_internal: bool = True):
        await get_current_user(request)
        query = {"ticket_id": ticket_id}
        if not include_internal:
            query["is_internal"] = False
        replies = await db.ticket_replies.find(query, {"_id": 0}).sort("created_at", 1).to_list(100)
        return replies

    # ============ Ticket Activity ============

    @api_router.get("/support/tickets/{ticket_id}/activity")
    async def get_ticket_activity(ticket_id: str, request: Request):
        await get_current_user(request)
        activity = await db.ticket_activity.find({"ticket_id": ticket_id}, {"_id": 0}).sort("timestamp", -1).to_list(50)
        return activity

    # ============ Support Queue / Dashboard ============

    @api_router.get("/support/dashboard")
    async def get_support_dashboard(request: Request):
        """Agent dashboard — queue overview"""
        await get_current_user(request)
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        open_count = await db.support_tickets.count_documents({"status": "open"})
        in_progress = await db.support_tickets.count_documents({"status": "in_progress"})
        waiting_customer = await db.support_tickets.count_documents({"status": "waiting_on_customer"})
        waiting_support = await db.support_tickets.count_documents({"status": "waiting_on_support"})
        resolved_today = await db.support_tickets.count_documents({"status": "resolved", "resolved_at": {"$gte": today}})
        total_open = open_count + in_progress + waiting_customer + waiting_support

        # SLA metrics
        sla_breached = await db.support_tickets.count_documents({"$or": [{"sla_first_response_breached": True}, {"sla_resolution_breached": True}], "status": {"$nin": ["resolved", "closed"]}})

        # Priority breakdown of open tickets
        priority_pipeline = [
            {"$match": {"status": {"$nin": ["resolved", "closed"]}}},
            {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
        ]
        priorities = {d["_id"]: d["count"] async for d in db.support_tickets.aggregate(priority_pipeline)}

        # Type breakdown
        type_pipeline = [
            {"$match": {"status": {"$nin": ["resolved", "closed"]}}},
            {"$group": {"_id": "$ticket_type", "count": {"$sum": 1}}}
        ]
        types = {d["_id"]: d["count"] async for d in db.support_tickets.aggregate(type_pipeline)}

        # Avg resolution time (last 30 days)
        thirty_ago = (now - timedelta(days=30)).isoformat()
        resolved_pipeline = [
            {"$match": {"status": {"$in": ["resolved", "closed"]}, "resolved_at": {"$gte": thirty_ago}}},
            {"$limit": 100}
        ]
        resolved_tickets = await db.support_tickets.aggregate(resolved_pipeline).to_list(100)
        avg_resolution_hours = 0
        if resolved_tickets:
            total_hours = 0
            count = 0
            for t in resolved_tickets:
                if t.get("resolved_at") and t.get("created_at"):
                    try:
                        created = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                        resolved = datetime.fromisoformat(t["resolved_at"].replace("Z", "+00:00"))
                        total_hours += (resolved - created).total_seconds() / 3600
                        count += 1
                    except Exception as _e:
                        logger.warning(f"Caught exception: {_e}")
            avg_resolution_hours = round(total_hours / max(count, 1), 1)

        return {
            "queue": {"open": open_count, "in_progress": in_progress, "waiting_on_customer": waiting_customer, "waiting_on_support": waiting_support, "total_open": total_open},
            "resolved_today": resolved_today,
            "sla_breached": sla_breached,
            "priority_breakdown": priorities,
            "type_breakdown": types,
            "avg_resolution_hours": avg_resolution_hours,
        }

    # ============ SLA Policies ============

    @api_router.get("/support/sla-policies")
    async def get_sla_policies(request: Request):
        await get_current_user(request)
        return {"policies": [
            {"key": k, "first_response_hours": v["first_response_hours"], "resolution_hours": v["resolution_hours"]}
            for k, v in SLA_TARGETS.items()
        ]}

    @api_router.put("/support/tickets/{ticket_id}/sla")
    async def set_ticket_sla(ticket_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        policy = body.get("sla_policy", "standard")
        if policy not in SLA_TARGETS:
            raise HTTPException(400, f"Invalid SLA policy. Use: {list(SLA_TARGETS.keys())}")
        await db.support_tickets.update_one({"ticket_id": ticket_id}, {"$set": {"sla_policy": policy}})
        return {"ticket_id": ticket_id, "sla_policy": policy, "targets": SLA_TARGETS[policy]}

    # ============ Knowledge Base Integration ============

    @api_router.get("/support/suggested-articles")
    async def get_suggested_articles(request: Request, query: str = ""):
        """Suggest KB articles based on ticket content"""
        await get_current_user(request)
        if not query:
            return {"articles": []}
        # Search workspace memory for relevant articles
        from nexus_utils import now_iso, safe_regex
        results = await db.workspace_memory.find(
            {"$or": [{"key": {"$regex": safe_regex(query), "$options": "i"}}, {"value": {"$regex": safe_regex(query), "$options": "i"}}]},
            {"_id": 0, "memory_id": 1, "key": 1, "value": 1, "category": 1}
        ).limit(5).to_list(5)
        return {"articles": results}

    # ============ Config ============

    @api_router.get("/support/config")
    async def get_support_config(request: Request):
        await get_current_user(request)
        return {
            "statuses": VALID_TICKET_STATUSES,
            "priorities": VALID_TICKET_PRIORITIES,
            "ticket_types": VALID_TICKET_TYPES,
            "sla_policies": list(SLA_TARGETS.keys()),
            "categories": ["general", "billing", "technical", "account", "feature", "integration"],
        }


    # ============ Ticket Attachments ============

    @api_router.post("/support/tickets/{ticket_id}/attachments")
    async def add_ticket_attachment(ticket_id: str, request: Request):
        user = await get_current_user(request)
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file provided")
        import base64
        content = await file.read()
        att_id = f"tkatt_{uuid.uuid4().hex[:8]}"
        now = now_iso()
        att = {
            "attachment_id": att_id, "ticket_id": ticket_id,
            "filename": file.filename or "attachment",
            "mime_type": file.content_type or "application/octet-stream",
            "size": len(content), "data": base64.b64encode(content).decode("utf-8"),
            "uploaded_by": user["user_id"], "uploaded_at": now,
        }
        await db.ticket_attachments.insert_one(att)
        return {k: v for k, v in att.items() if k not in ("_id", "data")}

    @api_router.get("/support/tickets/{ticket_id}/attachments")
    async def list_ticket_attachments(ticket_id: str, request: Request):
        await get_current_user(request)
        atts = await db.ticket_attachments.find({"ticket_id": ticket_id}, {"_id": 0, "data": 0}).to_list(20)
        return atts

    @api_router.get("/support/ticket-attachments/{att_id}")
    async def get_ticket_attachment(att_id: str, request: Request):
        await get_current_user(request)
        att = await db.ticket_attachments.find_one({"attachment_id": att_id}, {"_id": 0})
        if not att:
            raise HTTPException(404, "Attachment not found")
        return att

    # ============ Ticket Queues (by type) ============

    @api_router.get("/support/queues")
    async def get_support_queues(request: Request):
        """Get ticket counts per queue (ticket type)"""
        await get_current_user(request)
        pipeline = [
            {"$match": {"status": {"$nin": ["resolved", "closed"]}}},
            {"$group": {"_id": "$ticket_type", "count": {"$sum": 1}, "urgent": {"$sum": {"$cond": [{"$eq": ["$priority", "urgent"]}, 1, 0]}}}}
        ]
        queues = []
        async for doc in db.support_tickets.aggregate(pipeline):
            queues.append({"queue": doc["_id"], "count": doc["count"], "urgent": doc["urgent"]})
        # Ensure all types present
        existing = {q["queue"] for q in queues}
        for t in VALID_TICKET_TYPES:
            if t not in existing:
                queues.append({"queue": t, "count": 0, "urgent": 0})
        queues.sort(key=lambda x: x["count"], reverse=True)
        return {"queues": queues}

    @api_router.get("/support/queues/{queue_type}")
    async def get_queue_tickets(queue_type: str, request: Request, status: Optional[str] = None):
        """Get tickets in a specific queue"""
        await get_current_user(request)
        query = {"ticket_type": queue_type}
        if status:
            query["status"] = status
        else:
            query["status"] = {"$nin": ["resolved", "closed"]}
        tickets = await db.support_tickets.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"queue": queue_type, "tickets": tickets, "total": len(tickets)}
