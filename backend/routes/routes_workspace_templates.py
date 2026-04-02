"""Workspace Templates — Pre-built workspace configurations that users can clone.

Includes channel setup, agent configs, directives, project structures, and workflows.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)


MARKETPLACE_TEMPLATES = [
    {
        "template_id": "tpl_saas_startup",
        "name": "SaaS Startup",
        "description": "Full-stack AI team for building a SaaS product. Includes frontend, backend, DevOps, and PM channels.",
        "category": "Engineering",
        "channels": [
            {"name": "general", "agents": ["chatgpt", "claude"]},
            {"name": "frontend", "agents": ["chatgpt", "gemini"]},
            {"name": "backend", "agents": ["claude", "deepseek"]},
            {"name": "devops", "agents": ["chatgpt", "grok"]},
            {"name": "code-review", "agents": ["claude", "chatgpt", "deepseek"]},
        ],
        "directives": ["Follow SOLID principles", "Write comprehensive tests", "Document all APIs"],
        "projects": [{"name": "MVP Development", "tasks": ["Setup project", "Design database", "Build API", "Build UI", "Write tests", "Deploy"]}],
        "tags": ["engineering", "saas", "startup"],
        "popularity": 95,
    },
    {
        "template_id": "tpl_content_team",
        "name": "Content Creation Studio",
        "description": "AI-powered content team for blogs, social media, and marketing.",
        "category": "Marketing",
        "channels": [
            {"name": "brainstorm", "agents": ["chatgpt", "claude", "gemini"]},
            {"name": "writing", "agents": ["claude", "chatgpt"]},
            {"name": "social-media", "agents": ["chatgpt", "gemini"]},
            {"name": "seo", "agents": ["perplexity", "chatgpt"]},
        ],
        "directives": ["Match brand voice guidelines", "Include SEO keywords naturally", "Optimize for engagement"],
        "projects": [{"name": "Content Calendar", "tasks": ["Research topics", "Write drafts", "Review and edit", "Schedule posts"]}],
        "tags": ["content", "marketing", "social"],
        "popularity": 87,
    },
    {
        "template_id": "tpl_research",
        "name": "Research Lab",
        "description": "Multi-model research team for deep analysis, literature review, and report generation.",
        "category": "Research",
        "channels": [
            {"name": "research", "agents": ["claude", "perplexity", "gemini"]},
            {"name": "analysis", "agents": ["chatgpt", "claude", "deepseek"]},
            {"name": "reports", "agents": ["claude", "chatgpt"]},
        ],
        "directives": ["Cite sources", "Cross-verify facts across models", "Flag disagreements"],
        "projects": [{"name": "Research Project", "tasks": ["Define scope", "Literature review", "Data analysis", "Write report", "Peer review"]}],
        "tags": ["research", "analysis", "academic"],
        "popularity": 78,
    },
    {
        "template_id": "tpl_security_audit",
        "name": "Security Audit Team",
        "description": "AI security team for code review, vulnerability scanning, and compliance checks.",
        "category": "Security",
        "channels": [
            {"name": "security-review", "agents": ["claude", "chatgpt", "deepseek"]},
            {"name": "compliance", "agents": ["claude", "chatgpt"]},
            {"name": "incident-response", "agents": ["chatgpt", "grok"]},
        ],
        "directives": ["Check OWASP Top 10", "Verify input sanitization", "Review auth flows", "Check for hardcoded secrets"],
        "projects": [{"name": "Security Audit", "tasks": ["Code scan", "Dependency audit", "Auth review", "Data flow analysis", "Report"]}],
        "tags": ["security", "audit", "compliance"],
        "popularity": 72,
    },
    {
        "template_id": "tpl_data_pipeline",
        "name": "Data Engineering Pipeline",
        "description": "AI team for building data pipelines, ETL, analytics, and ML models.",
        "category": "Data",
        "channels": [
            {"name": "data-engineering", "agents": ["deepseek", "chatgpt"]},
            {"name": "analytics", "agents": ["chatgpt", "gemini"]},
            {"name": "ml-models", "agents": ["claude", "deepseek"]},
        ],
        "directives": ["Optimize for query performance", "Handle edge cases in data", "Document transformations"],
        "projects": [{"name": "Data Pipeline", "tasks": ["Schema design", "ETL development", "Testing", "Dashboard creation"]}],
        "tags": ["data", "analytics", "ml"],
        "popularity": 68,
    },
]


def register_workspace_templates_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.get("/workspace-templates/marketplace")
    async def list_templates(request: Request, category: str = None):
        user = await get_current_user(request)
        templates = MARKETPLACE_TEMPLATES
        if category:
            templates = [t for t in templates if t["category"].lower() == category.lower()]
        
        # Also get community templates
        community = await db.workspace_templates.find(
            {"published": True}, {"_id": 0}
        ).sort("popularity", -1).limit(20).to_list(20)
        
        return {
            "official": sorted(templates, key=lambda x: x["popularity"], reverse=True),
            "community": community,
            "categories": list(set(t["category"] for t in MARKETPLACE_TEMPLATES)),
        }

    @api_router.post("/workspace-templates/marketplace/{template_id}/clone")
    async def clone_template(template_id: str, request: Request):
        """Clone a template into a new workspace with all channels, agents, directives, and projects."""
        user = await get_current_user(request)
        body = await request.json()
        
        template = next((t for t in MARKETPLACE_TEMPLATES if t["template_id"] == template_id), None)
        if not template:
            template = await db.workspace_templates.find_one({"template_id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(404, "Template not found")
        
        ws_name = body.get("name", template["name"])
        now = now_iso()
        ws_id = f"ws_{uuid.uuid4().hex[:12]}"
        
        # Create workspace
        workspace = {
            "workspace_id": ws_id,
            "name": ws_name,
            "description": template.get("description", ""),
            "owner_id": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "template_source": template_id,
        }
        await db.workspaces.insert_one(workspace)
        
        # Create channels
        created_channels = []
        for ch_cfg in template.get("channels") or []:
            ch_id = f"ch_{uuid.uuid4().hex[:12]}"
            channel = {
                "channel_id": ch_id,
                "workspace_id": ws_id,
                "name": ch_cfg["name"],
                "ai_agents": ch_cfg.get("agents") or [],
                "created_by": user["user_id"],
                "created_at": now,
            }
            await db.channels.insert_one(channel)
            created_channels.append(ch_id)
        
        # Create projects and tasks
        for proj_cfg in template.get("projects") or []:
            proj_id = f"proj_{uuid.uuid4().hex[:12]}"
            await db.projects.insert_one({
                "project_id": proj_id, "workspace_id": ws_id,
                "name": proj_cfg["name"], "status": "active",
                "created_by": user["user_id"], "created_at": now,
            })
            for i, task_title in enumerate(proj_cfg.get("tasks") or []):
                await db.project_tasks.insert_one({
                    "task_id": f"task_{uuid.uuid4().hex[:12]}",
                    "project_id": proj_id, "workspace_id": ws_id,
                    "title": task_title, "status": "todo",
                    "priority": "medium", "order": i,
                    "created_by": user["user_id"], "created_at": now,
                })
        
        # Add directives
        for directive in template.get("directives") or []:
            await db.directives.insert_one({
                "directive_id": f"dir_{uuid.uuid4().hex[:12]}",
                "workspace_id": ws_id,
                "content": directive,
                "active": True,
                "created_by": user["user_id"],
                "created_at": now,
            })
        
        workspace.pop("_id", None)
        return {
            "workspace": workspace,
            "channels_created": len(created_channels),
            "projects_created": len(template.get("projects") or []),
            "directives_created": len(template.get("directives") or []),
        }

    @api_router.post("/workspace-templates/marketplace/publish")
    async def publish_template(request: Request):
        """Publish a workspace as a community template."""
        user = await get_current_user(request)
        body = await request.json()
        ws_id = body.get("workspace_id", "")
        
        workspace = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        channels = await db.channels.find({"workspace_id": ws_id}, {"_id": 0, "name": 1, "ai_agents": 1}).to_list(20)
        
        template = {
            "template_id": f"tpl_{uuid.uuid4().hex[:12]}",
            "name": body.get("name", workspace["name"]),
            "description": body.get("description", workspace.get("description", "")),
            "category": body.get("category", "General"),
            "channels": [{"name": c["name"], "agents": c.get("ai_agents") or []} for c in channels],
            "tags": body.get("tags") or [],
            "published": True,
            "popularity": 0,
            "created_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.workspace_templates.insert_one(template)
        template.pop("_id", None)
        return template
