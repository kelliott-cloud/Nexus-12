"""Enhancements — Usage Analytics, Smart Summarization, Comments, Activity Feed, Workspace Templates,
Agent Personas, Conversation Branching, @channel Notifications, Activity Timeline"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


# ============ Models ============

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class PersonaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    base_model: str = "claude"
    system_prompt: str = Field(..., min_length=10)
    category: str = "general"  # general, code_review, writing, research, data, strategy
    is_public: bool = False

class WorkspaceTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    category: str = "general"
    channels: List[dict] = []
    suggested_agents: List[str] = []
    suggested_workflows: List[str] = []


PERSONA_CATEGORIES = ["general", "code_review", "writing", "research", "data", "strategy"]

# Pre-built workspace templates
BUILTIN_WS_TEMPLATES = [
    {"template_id": "wst_product_launch", "name": "Product Launch", "description": "Channels for research, messaging, GTM planning, and launch execution.", "category": "marketing",
     "channels": [{"name": "market-research", "agents": ["perplexity", "gemini"]}, {"name": "messaging-copy", "agents": ["claude", "chatgpt"]}, {"name": "gtm-strategy", "agents": ["claude", "chatgpt", "gemini"]}],
     "suggested_agents": ["claude", "chatgpt", "perplexity", "gemini"]},
    {"template_id": "wst_code_review", "name": "Code Review Team", "description": "Multi-AI code review with analysis, refactoring, and testing channels.", "category": "development",
     "channels": [{"name": "code-review", "agents": ["claude", "deepseek"]}, {"name": "refactoring", "agents": ["chatgpt", "deepseek"]}, {"name": "testing", "agents": ["claude", "chatgpt"]}],
     "suggested_agents": ["claude", "chatgpt", "deepseek"]},
    {"template_id": "wst_research_lab", "name": "Research Lab", "description": "Deep research with source gathering, analysis, and synthesis.", "category": "research",
     "channels": [{"name": "source-gathering", "agents": ["perplexity", "gemini"]}, {"name": "analysis", "agents": ["claude", "chatgpt"]}, {"name": "synthesis", "agents": ["claude"]}],
     "suggested_agents": ["perplexity", "gemini", "claude", "chatgpt"]},
    {"template_id": "wst_content_studio", "name": "Content Studio", "description": "Content creation pipeline with ideation, drafting, and editing.", "category": "content",
     "channels": [{"name": "ideation", "agents": ["chatgpt", "gemini"]}, {"name": "drafting", "agents": ["claude", "chatgpt"]}, {"name": "editing-review", "agents": ["claude", "mistral"]}],
     "suggested_agents": ["claude", "chatgpt", "gemini", "mistral"]},
]

# Pre-built agent personas
BUILTIN_PERSONAS = [
    {"persona_id": "per_sr_code_reviewer", "name": "Senior Code Reviewer", "description": "Thorough code reviewer focused on bugs, security, and best practices", "base_model": "claude", "category": "code_review",
     "system_prompt": "You are a senior code reviewer with 15+ years of experience. Review code for bugs, security vulnerabilities, performance issues, and adherence to best practices. Be thorough but constructive. Always suggest specific improvements with code examples.", "is_public": True},
    {"persona_id": "per_tech_writer", "name": "Technical Writer", "description": "Clear, concise technical documentation specialist", "base_model": "chatgpt", "category": "writing",
     "system_prompt": "You are a technical writer specializing in developer documentation. Write clear, concise, and well-structured documentation. Use consistent formatting, include code examples, and anticipate reader questions. Follow the docs-as-code philosophy.", "is_public": True},
    {"persona_id": "per_data_analyst", "name": "Data Analyst", "description": "Statistical analysis and data interpretation expert", "base_model": "gemini", "category": "data",
     "system_prompt": "You are a senior data analyst. Analyze data thoroughly, identify trends and patterns, calculate relevant statistics, and present findings clearly. Always question assumptions and validate data quality. Provide actionable insights.", "is_public": True},
    {"persona_id": "per_strategist", "name": "Business Strategist", "description": "Strategic thinker focused on competitive analysis and growth", "base_model": "claude", "category": "strategy",
     "system_prompt": "You are a business strategist with expertise in competitive analysis, market positioning, and growth strategy. Think frameworks: Porter's Five Forces, SWOT, Jobs-to-be-Done. Always ground recommendations in evidence and consider second-order effects.", "is_public": True},
]


def register_enhancement_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ 1. Usage Analytics Dashboard ============

    @api_router.get("/workspaces/{workspace_id}/usage-analytics")
    async def get_usage_analytics(workspace_id: str, request: Request, days: int = 30):
        """Get detailed usage analytics for a workspace"""
        user = await _authed_user(request, workspace_id)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Message counts by type
        msg_pipeline = [
            {"$match": {"channel_id": {"$in": [ch["channel_id"] async for ch in db.channels.find({"workspace_id": workspace_id}, {"channel_id": 1, "_id": 0})]}}},
            {"$group": {"_id": "$sender_type", "count": {"$sum": 1}}}
        ]
        msg_counts = {d["_id"]: d["count"] async for d in db.messages.aggregate(msg_pipeline)}

        # AI model usage
        model_pipeline = [
            {"$match": {"workspace_id": workspace_id, "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$agent", "calls": {"$sum": 1}, "avg_ms": {"$avg": "$response_time_ms"}, "total_content": {"$sum": "$content_length"}}}
        ]
        model_usage = []
        async for d in db.analytics.aggregate(model_pipeline):
            model_usage.append({"model": d["_id"], "calls": d["calls"], "avg_response_ms": round(d.get("avg_ms") or 0), "total_chars": d.get("total_content", 0)})

        # Daily activity
        daily_pipeline = [
            {"$match": {"workspace_id": workspace_id, "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": {"$substr": ["$timestamp", 0, 10]}, "count": {"$sum": 1}}}
        ]
        daily = [{"date": d["_id"], "count": d["count"]} async for d in db.analytics.aggregate(daily_pipeline)]

        artifacts_count = await db.artifacts.count_documents({"workspace_id": workspace_id})
        workflows_count = await db.workflows.count_documents({"workspace_id": workspace_id})

        return {
            "period_days": days,
            "messages": {"human": msg_counts.get("human", 0), "ai": msg_counts.get("ai", 0), "system": msg_counts.get("system", 0), "total": sum(msg_counts.values())},
            "model_usage": sorted(model_usage, key=lambda x: x["calls"], reverse=True),
            "daily_activity": sorted(daily, key=lambda x: x["date"]),
            "artifacts_count": artifacts_count,
            "workflows_count": workflows_count,
        }

    # ============ 6. Smart Summarization ============

    @api_router.post("/channels/{channel_id}/summarize")
    async def summarize_channel(channel_id: str, request: Request):
        """One-click summarize a channel conversation"""
        user = await get_current_user(request)
        from nexus_utils import require_channel_access
        await require_channel_access(db, user, channel_id)
        messages = await db.messages.find(
            {"channel_id": channel_id, "sender_type": {"$in": ["human", "ai"]}},
            {"_id": 0, "sender_name": 1, "content": 1, "sender_type": 1}
        ).sort("created_at", 1).to_list(100)

        if not messages:
            return {"summary": "No messages to summarize.", "total_messages": 0, "agents_involved": [], "key_decisions": [], "action_items": [], "open_questions": []}

        # Build conversation text for potential future AI summarization
        # conv = "\n".join(...)  # Reserved for AI-powered summarization

        # Extract structured summary heuristically
        key_decisions = []
        action_items = []
        open_questions = []

        for m in messages:
            content = m.get("content", "").lower()
            if any(w in content for w in ["decided", "agreed", "conclusion", "we'll go with", "let's use"]):
                key_decisions.append(m["content"][:200])
            if any(w in content for w in ["todo", "action item", "need to", "should", "must", "will do"]):
                action_items.append(m["content"][:200])
            if "?" in m.get("content", "") and m["sender_type"] == "human":
                open_questions.append(m["content"][:200])

        # Build summary
        total = len(messages)
        ai_count = sum(1 for m in messages if m["sender_type"] == "ai")
        agents = list({m["sender_name"] for m in messages if m["sender_type"] == "ai"})

        summary = f"Conversation with {total} messages ({ai_count} from AI agents: {', '.join(agents[:5])}). "
        if key_decisions:
            summary += f"{len(key_decisions)} key decision(s) identified. "
        if action_items:
            summary += f"{len(action_items)} action item(s). "
        if open_questions:
            summary += f"{len(open_questions)} open question(s)."

        return {
            "summary": summary,
            "total_messages": total,
            "agents_involved": agents,
            "key_decisions": key_decisions[:5],
            "action_items": action_items[:5],
            "open_questions": open_questions[:5],
        }

    # ============ 7. Comments on Artifacts ============

    @api_router.post("/artifacts/{artifact_id}/comments")
    async def add_comment(artifact_id: str, data: CommentCreate, request: Request):
        user = await get_current_user(request)
        artifact = await db.artifacts.find_one({"artifact_id": artifact_id})
        if not artifact:
            raise HTTPException(404, "Artifact not found")
        comment_id = f"cmt_{uuid.uuid4().hex[:12]}"
        comment = {
            "comment_id": comment_id, "artifact_id": artifact_id,
            "content": data.content, "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.artifact_comments.insert_one(comment)
        return {k: v for k, v in comment.items() if k != "_id"}

    @api_router.get("/artifacts/{artifact_id}/comments")
    async def list_comments(artifact_id: str, request: Request):
        user = await get_current_user(request)
        comments = await db.artifact_comments.find({"artifact_id": artifact_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
        return comments

    @api_router.delete("/comments/{comment_id}")
    async def delete_comment(comment_id: str, request: Request):
        user = await get_current_user(request)
        result = await db.artifact_comments.delete_one({"comment_id": comment_id, "author_id": user["user_id"]})
        if result.deleted_count == 0:
            raise HTTPException(404, "Comment not found or not yours")
        return {"message": "Deleted"}

    # ============ 5. Agent Personas Library ============

    @api_router.get("/personas")
    async def list_personas(request: Request, category: Optional[str] = None):
        await get_current_user(request)
        # Combine built-in + user-created
        personas = list(BUILTIN_PERSONAS)
        query = {"is_public": True}
        if category:
            query["category"] = category
        custom = await db.personas.find(query, {"_id": 0}).to_list(50)
        personas.extend(custom)
        return {"personas": personas, "categories": PERSONA_CATEGORIES}

    @api_router.post("/personas")
    async def create_persona(data: PersonaCreate, request: Request):
        user = await get_current_user(request)
        persona_id = f"per_{uuid.uuid4().hex[:12]}"
        persona = {
            "persona_id": persona_id, "name": data.name, "description": data.description,
            "base_model": data.base_model, "system_prompt": data.system_prompt,
            "category": data.category if data.category in PERSONA_CATEGORIES else "general",
            "is_public": data.is_public, "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.personas.insert_one(persona)
        return {k: v for k, v in persona.items() if k != "_id"}

    @api_router.delete("/personas/{persona_id}")
    async def delete_persona(persona_id: str, request: Request):
        user = await get_current_user(request)
        result = await db.personas.delete_one({"persona_id": persona_id, "created_by": user["user_id"]})
        if result.deleted_count == 0:
            raise HTTPException(404, "Persona not found or not yours")
        return {"message": "Deleted"}

    # ============ 2. Workspace Templates ============

    @api_router.get("/workspace-templates")
    async def list_workspace_templates(request: Request):
        await get_current_user(request)
        custom = await db.workspace_templates.find({}, {"_id": 0}).to_list(20)
        return {"templates": BUILTIN_WS_TEMPLATES + custom}

    @api_router.post("/workspace-templates/{template_id}/deploy")
    async def deploy_workspace_template(template_id: str, request: Request):
        """Deploy a workspace template — creates workspace with pre-configured channels"""
        user = await get_current_user(request)
        body = await request.json()
        ws_name = body.get("name", "")

        # Find template
        tpl = next((t for t in BUILTIN_WS_TEMPLATES if t["template_id"] == template_id), None)
        if not tpl:
            tpl = await db.workspace_templates.find_one({"template_id": template_id}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")

        # Create workspace
        workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        workspace = {
            "workspace_id": workspace_id, "name": ws_name or tpl["name"],
            "description": tpl["description"], "owner_id": user["user_id"],
            "members": [user["user_id"]], "disabled": False,
            "template_id": template_id, "created_at": now,
        }
        await db.workspaces.insert_one(workspace)

        # Create channels
        for ch_def in tpl.get("channels") or []:
            ch_id = f"ch_{uuid.uuid4().hex[:12]}"
            await db.channels.insert_one({
                "channel_id": ch_id, "workspace_id": workspace_id,
                "name": ch_def["name"], "description": "",
                "ai_agents": ch_def.get("agents", ["claude", "chatgpt"]),
                "created_at": now,
            })

        return {"workspace_id": workspace_id, "name": workspace["name"], "channels_created": len(tpl.get("channels") or [])}

    # ============ 4. Conversation Branching ============

    @api_router.post("/channels/{channel_id}/branch")
    async def branch_conversation(channel_id: str, request: Request):
        """Fork a channel conversation into a new branch channel"""
        user = await get_current_user(request)
        from nexus_utils import require_channel_access
        await require_channel_access(db, user, channel_id)
        body = await request.json()
        branch_name = body.get("name", "")

        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")

        # Copy messages up to this point
        messages = await db.messages.find({"channel_id": channel_id}, {"_id": 0}).sort("created_at", 1).to_list(100)

        # Create branch channel
        branch_id = f"ch_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        branch = {
            "channel_id": branch_id,
            "workspace_id": channel["workspace_id"],
            "name": branch_name or f"{channel['name']}-branch",
            "description": f"Branched from #{channel['name']}",
            "ai_agents": channel.get("ai_agents") or [],
            "branched_from": channel_id,
            "branch_point": len(messages),
            "created_at": now,
        }
        await db.channels.insert_one(branch)

        # Copy messages to branch
        for msg in messages:
            new_msg = {**msg, "message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": branch_id}
            await db.messages.insert_one(new_msg)

        return {"branch_channel_id": branch_id, "name": branch["name"], "messages_copied": len(messages)}

    # ============ 3. Team Activity Feed ============

    @api_router.get("/workspaces/{workspace_id}/activity-feed")
    async def get_activity_feed(workspace_id: str, request: Request, limit: int = 30):
        """Get recent activity across the workspace"""
        user = await _authed_user(request, workspace_id)

        events = []

        # Recent messages
        ch_ids = [ch["channel_id"] async for ch in db.channels.find({"workspace_id": workspace_id}, {"channel_id": 1, "_id": 0})]
        if ch_ids:
            recent_msgs = await db.messages.find(
                {"channel_id": {"$in": ch_ids}, "sender_type": {"$in": ["human", "ai"]}},
                {"_id": 0, "message_id": 1, "sender_name": 1, "sender_type": 1, "content": 1, "created_at": 1, "channel_id": 1}
            ).sort("created_at", -1).limit(10).to_list(10)
            for m in recent_msgs:
                events.append({"type": "message", "actor": m["sender_name"], "description": m["content"][:100], "timestamp": m["created_at"], "resource_id": m["message_id"]})

        # Recent artifacts
        recent_arts = await db.artifacts.find(
            {"workspace_id": workspace_id}, {"_id": 0, "artifact_id": 1, "name": 1, "created_by": 1, "created_at": 1}
        ).sort("created_at", -1).limit(5).to_list(5)
        for a in recent_arts:
            events.append({"type": "artifact_created", "actor": a["created_by"], "description": f"Created artifact: {a['name']}", "timestamp": a["created_at"], "resource_id": a["artifact_id"]})

        # Recent tasks
        recent_tasks = await db.project_tasks.find(
            {"workspace_id": workspace_id}, {"_id": 0, "task_id": 1, "title": 1, "status": 1, "created_at": 1, "updated_at": 1}
        ).sort("updated_at", -1).limit(5).to_list(5)
        for t in recent_tasks:
            events.append({"type": "task_updated", "actor": "system", "description": f"Task '{t['title']}' — {t['status']}", "timestamp": t["updated_at"], "resource_id": t["task_id"]})

        # Sort all by timestamp
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return {"events": events[:limit]}

    # ============ 9. Workspace Activity Timeline ============

    @api_router.get("/workspaces/{workspace_id}/timeline")
    async def get_workspace_timeline(workspace_id: str, request: Request, days: int = 7, limit: int = 50):
        """Visual timeline of all workspace events"""
        user = await _authed_user(request, workspace_id)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        timeline = []

        # Audit log entries
        audits = await db.audit_log.find(
            {"workspace_id": workspace_id, "timestamp": {"$gte": cutoff}}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        for a in audits:
            timeline.append({"type": "audit", "action": a["action"], "resource": a["resource_type"], "actor": a.get("user_name", a.get("user_id", "system")), "timestamp": a["timestamp"], "details": a.get("details") or {}})

        # Workflow runs
        wf_ids = [wf["workflow_id"] async for wf in db.workflows.find({"workspace_id": workspace_id}, {"workflow_id": 1, "_id": 0})]
        if wf_ids:
            runs = await db.workflow_runs.find(
                {"workflow_id": {"$in": wf_ids}, "created_at": {"$gte": cutoff}}, {"_id": 0, "run_id": 1, "workflow_id": 1, "status": 1, "created_at": 1}
            ).sort("created_at", -1).limit(10).to_list(10)
            for r in runs:
                timeline.append({"type": "workflow_run", "action": r["status"], "resource": r["workflow_id"], "actor": "system", "timestamp": r["created_at"]})

        timeline.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return {"timeline": timeline[:limit], "period_days": days}

    # ============ 8. @channel Notifications ============

    @api_router.post("/workspaces/{workspace_id}/notify")
    async def send_workspace_notification(workspace_id: str, request: Request):
        """Send a notification to specific workspace members"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        message = body.get("message", "")
        target_user_ids = body.get("user_ids") or []  # Empty = all members
        notification_type = body.get("type", "info")  # info, task, workflow, alert

        if not message:
            raise HTTPException(400, "Message required")

        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")

        recipients = target_user_ids if target_user_ids else workspace.get("members") or []
        now = datetime.now(timezone.utc).isoformat()

        for uid in recipients:
            if uid == user["user_id"]:
                continue
            await db.notifications.insert_one({
                "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
                "user_id": uid, "type": notification_type,
                "title": f"From {user.get('name', 'Someone')} in {workspace['name']}",
                "message": message, "read": False,
                "workspace_id": workspace_id,
                "created_at": now,
            })

        return {"sent_to": len(recipients), "message": message}
