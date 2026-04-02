"""Ideation Module — Brainstorming, feature specs, wireframes, and prototype briefs."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def register_ideation_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Idea Canvas ============

    @api_router.post("/workspaces/{workspace_id}/ideas")
    async def create_idea(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        idea = {
            "idea_id": f"idea_{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "title": body.get("title", "").strip(),
            "description": body.get("description", ""),
            "goals": body.get("goals") or [],
            "target_audience": body.get("target_audience", ""),
            "tags": body.get("tags") or [],
            "status": body.get("status", "concept"),  # concept, exploring, spec-ready, building, done
            "priority": body.get("priority", "medium"),
            "references": body.get("references") or [],  # {type: "link"|"image"|"doc", url, title}
            "created_by": user["user_id"],
            "created_by_name": user.get("name", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not idea["title"]:
            raise HTTPException(400, "Title required")
        await db.ideas.insert_one(idea)
        idea.pop("_id", None)
        return idea

    @api_router.get("/workspaces/{workspace_id}/ideas")
    async def list_ideas(workspace_id: str, request: Request, status: str = None):
        await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if status:
            query["status"] = status
        ideas = await db.ideas.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
        return {"ideas": ideas}

    @api_router.get("/ideas/{idea_id}")
    async def get_idea(idea_id: str, request: Request):
        await get_current_user(request)
        idea = await db.ideas.find_one({"idea_id": idea_id}, {"_id": 0})
        if not idea:
            raise HTTPException(404, "Idea not found")
        # Get linked specs and wireframes
        specs = await db.feature_specs.find({"idea_id": idea_id}, {"_id": 0}).to_list(50)
        wireframes = await db.wireframes.find({"idea_id": idea_id}, {"_id": 0}).to_list(20)
        idea["specs"] = specs
        idea["wireframes"] = wireframes
        return idea

    @api_router.put("/ideas/{idea_id}")
    async def update_idea(idea_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for field in ["title", "description", "goals", "target_audience", "tags", "status", "priority", "references"]:
            if field in body:
                updates[field] = body[field]
        await db.ideas.update_one({"idea_id": idea_id}, {"$set": updates})
        return await db.ideas.find_one({"idea_id": idea_id}, {"_id": 0})

    @api_router.delete("/ideas/{idea_id}")
    async def delete_idea(idea_id: str, request: Request):
        await get_current_user(request)
        await db.ideas.delete_one({"idea_id": idea_id})
        await db.feature_specs.delete_many({"idea_id": idea_id})
        await db.wireframes.delete_many({"idea_id": idea_id})
        return {"deleted": True}

    # ============ Feature Spec Builder ============

    @api_router.post("/ideas/{idea_id}/specs")
    async def create_spec(idea_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        spec = {
            "spec_id": f"spec_{uuid.uuid4().hex[:12]}",
            "idea_id": idea_id,
            "title": body.get("title", "").strip(),
            "user_stories": body.get("user_stories") or [],  # [{as_a, i_want, so_that}]
            "features": body.get("features") or [],  # [{name, description, priority: must|nice|future, acceptance_criteria: []}]
            "tech_requirements": body.get("tech_requirements") or [],
            "constraints": body.get("constraints") or [],
            "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not spec["title"]:
            raise HTTPException(400, "Spec title required")
        await db.feature_specs.insert_one(spec)
        spec.pop("_id", None)
        return spec

    @api_router.get("/ideas/{idea_id}/specs")
    async def list_specs(idea_id: str, request: Request):
        await get_current_user(request)
        specs = await db.feature_specs.find({"idea_id": idea_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"specs": specs}

    @api_router.put("/specs/{spec_id}")
    async def update_spec(spec_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for field in ["title", "user_stories", "features", "tech_requirements", "constraints"]:
            if field in body:
                updates[field] = body[field]
        await db.feature_specs.update_one({"spec_id": spec_id}, {"$set": updates})
        return await db.feature_specs.find_one({"spec_id": spec_id}, {"_id": 0})

    @api_router.delete("/specs/{spec_id}")
    async def delete_spec(spec_id: str, request: Request):
        await get_current_user(request)
        await db.feature_specs.delete_one({"spec_id": spec_id})
        return {"deleted": True}

    # ============ Wireframe Sketcher ============

    @api_router.post("/ideas/{idea_id}/wireframes")
    async def create_wireframe(idea_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        wireframe = {
            "wireframe_id": f"wf_{uuid.uuid4().hex[:12]}",
            "idea_id": idea_id,
            "name": body.get("name", "Untitled Screen"),
            "screen_type": body.get("screen_type", "page"),  # page, modal, drawer, component
            "components": body.get("components") or [],  # [{type, x, y, w, h, label, props}]
            "connections": body.get("connections") or [],  # [{from_screen, to_screen, trigger}]
            "svg_export": body.get("svg_export", ""),
            "notes": body.get("notes", ""),
            "order": body.get("order", 0),
            "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.wireframes.insert_one(wireframe)
        wireframe.pop("_id", None)
        return wireframe

    @api_router.get("/ideas/{idea_id}/wireframes")
    async def list_wireframes(idea_id: str, request: Request):
        await get_current_user(request)
        wfs = await db.wireframes.find({"idea_id": idea_id}, {"_id": 0}).sort("order", 1).to_list(50)
        return {"wireframes": wfs}

    @api_router.put("/wireframes/{wireframe_id}")
    async def update_wireframe(wireframe_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for field in ["name", "screen_type", "components", "connections", "svg_export", "notes", "order"]:
            if field in body:
                updates[field] = body[field]
        await db.wireframes.update_one({"wireframe_id": wireframe_id}, {"$set": updates})
        return await db.wireframes.find_one({"wireframe_id": wireframe_id}, {"_id": 0})

    @api_router.delete("/wireframes/{wireframe_id}")
    async def delete_wireframe(wireframe_id: str, request: Request):
        await get_current_user(request)
        await db.wireframes.delete_one({"wireframe_id": wireframe_id})
        return {"deleted": True}

    # ============ Prototype Brief Generator ============

    @api_router.post("/ideas/{idea_id}/generate-brief")
    async def generate_brief(idea_id: str, request: Request):
        """Auto-generate a structured AI prompt from the ideation work."""
        await get_current_user(request)
        idea = await db.ideas.find_one({"idea_id": idea_id}, {"_id": 0})
        if not idea:
            raise HTTPException(404, "Idea not found")

        specs = await db.feature_specs.find({"idea_id": idea_id}, {"_id": 0}).to_list(20)
        wireframes = await db.wireframes.find({"idea_id": idea_id}, {"_id": 0}).to_list(20)

        brief = f"# Project Brief: {idea['title']}\n\n"
        brief += f"## Description\n{idea.get('description', 'N/A')}\n\n"

        if idea.get("goals"):
            brief += "## Goals\n"
            for g in idea["goals"]:
                brief += f"- {g}\n"
            brief += "\n"

        if idea.get("target_audience"):
            brief += f"## Target Audience\n{idea['target_audience']}\n\n"

        for spec in specs:
            brief += f"## Feature Spec: {spec['title']}\n\n"
            if spec.get("user_stories"):
                brief += "### User Stories\n"
                for story in spec["user_stories"]:
                    brief += f"- As a **{story.get('as_a', '?')}**, I want **{story.get('i_want', '?')}**, so that **{story.get('so_that', '?')}**\n"
                brief += "\n"
            if spec.get("features"):
                brief += "### Features\n"
                for feat in spec["features"]:
                    p = feat.get("priority", "medium")
                    brief += f"- [{p.upper()}] **{feat.get('name', '?')}**: {feat.get('description', '')}\n"
                    for ac in feat.get("acceptance_criteria") or []:
                        brief += f"  - [ ] {ac}\n"
                brief += "\n"
            if spec.get("tech_requirements"):
                brief += "### Technical Requirements\n"
                for req in spec["tech_requirements"]:
                    brief += f"- {req}\n"
                brief += "\n"
            if spec.get("constraints"):
                brief += "### Constraints\n"
                for c in spec["constraints"]:
                    brief += f"- {c}\n"
                brief += "\n"

        if wireframes:
            brief += "## Wireframes\n"
            for wf in wireframes:
                brief += f"- **{wf['name']}** ({wf.get('screen_type', 'page')})"
                if wf.get("components"):
                    brief += f" — {len(wf['components'])} components"
                if wf.get("notes"):
                    brief += f": {wf['notes']}"
                brief += "\n"
            brief += "\n"

        brief += "---\n*Generated by Nexus Ideation Module*\n"

        return {"brief": brief, "idea_id": idea_id, "word_count": len(brief.split())}

    @api_router.post("/ideas/{idea_id}/send-to-channel")
    async def send_brief_to_channel(idea_id: str, request: Request):
        """Generate brief and post it to a channel for AI agents to work on."""
        user = await get_current_user(request)
        body = await request.json()
        channel_id = body.get("channel_id", "")
        if not channel_id:
            raise HTTPException(400, "channel_id required")

        # Generate the brief
        idea = await db.ideas.find_one({"idea_id": idea_id}, {"_id": 0})
        if not idea:
            raise HTTPException(404, "Idea not found")

        specs = await db.feature_specs.find({"idea_id": idea_id}, {"_id": 0}).to_list(20)
        wireframes = await db.wireframes.find({"idea_id": idea_id}, {"_id": 0}).to_list(20)

        # Build concise brief for agents
        content = f"**Project Brief: {idea['title']}**\n\n"
        content += f"{idea.get('description', '')}\n\n"
        if idea.get("goals"):
            content += "**Goals:** " + " | ".join(idea["goals"]) + "\n\n"
        for spec in specs:
            content += f"**{spec['title']}:**\n"
            for feat in spec.get("features") or []:
                content += f"- [{feat.get('priority','?').upper()}] {feat.get('name','?')}: {feat.get('description','')}\n"
        if wireframes:
            content += f"\n**{len(wireframes)} wireframe screens** attached for reference.\n"

        # Post as a message
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        await db.messages.insert_one({
            "message_id": msg_id,
            "channel_id": channel_id,
            "sender_type": "human",
            "sender_id": user["user_id"],
            "sender_name": user.get("name", "Unknown"),
            "content": content,
            "idea_ref": idea_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Update idea status
        await db.ideas.update_one({"idea_id": idea_id}, {"$set": {"status": "building", "channel_id": channel_id}})

        return {"message_id": msg_id, "channel_id": channel_id, "brief_length": len(content)}

    # ============ Idea Gallery / Templates ============

    @api_router.get("/idea-templates")
    async def list_idea_templates(request: Request):
        await get_current_user(request)
        templates = await db.idea_templates.find({}, {"_id": 0}).sort("uses", -1).to_list(50)
        if not templates:
            # Seed default templates
            defaults = [
                {"template_id": "tpl_webapp", "name": "Web Application", "description": "Full-stack web app with auth, dashboard, and API",
                 "goals": ["User authentication", "Responsive UI", "REST API", "Database integration"],
                 "tags": ["web", "fullstack"], "features_template": [
                    {"name": "User Auth", "priority": "must", "description": "Registration, login, password reset"},
                    {"name": "Dashboard", "priority": "must", "description": "Main landing page after login"},
                    {"name": "API", "priority": "must", "description": "RESTful endpoints for CRUD operations"},
                 ], "uses": 0},
                {"template_id": "tpl_mobile", "name": "Mobile App", "description": "Cross-platform mobile application",
                 "goals": ["Native-feel UX", "Offline support", "Push notifications"],
                 "tags": ["mobile", "app"], "features_template": [
                    {"name": "Onboarding", "priority": "must", "description": "First-time user experience"},
                    {"name": "Core Feature", "priority": "must", "description": "Primary app functionality"},
                    {"name": "Settings", "priority": "nice", "description": "User preferences and account"},
                 ], "uses": 0},
                {"template_id": "tpl_api", "name": "API Service", "description": "Backend API with documentation",
                 "goals": ["RESTful design", "Authentication", "Rate limiting", "API docs"],
                 "tags": ["api", "backend"], "features_template": [
                    {"name": "Endpoints", "priority": "must", "description": "Core CRUD API routes"},
                    {"name": "Auth", "priority": "must", "description": "API key or OAuth authentication"},
                    {"name": "Docs", "priority": "nice", "description": "OpenAPI/Swagger documentation"},
                 ], "uses": 0},
                {"template_id": "tpl_landing", "name": "Landing Page", "description": "Marketing landing page with CTA",
                 "goals": ["Hero section", "Feature showcase", "Call to action", "Mobile responsive"],
                 "tags": ["marketing", "frontend"], "features_template": [
                    {"name": "Hero", "priority": "must", "description": "Above-the-fold headline and CTA"},
                    {"name": "Features", "priority": "must", "description": "Product feature grid"},
                    {"name": "Pricing", "priority": "nice", "description": "Pricing tiers comparison"},
                 ], "uses": 0},
            ]
            for t in defaults:
                await db.idea_templates.insert_one(t)
            templates = defaults
        return {"templates": [{k: v for k, v in t.items() if k != "_id"} for t in templates]}

    @api_router.post("/ideas/{idea_id}/clone-template/{template_id}")
    async def apply_template(idea_id: str, template_id: str, request: Request):
        await get_current_user(request)
        tpl = await db.idea_templates.find_one({"template_id": template_id}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if tpl.get("goals"):
            updates["goals"] = tpl["goals"]
        if tpl.get("tags"):
            updates["tags"] = tpl["tags"]
        await db.ideas.update_one({"idea_id": idea_id}, {"$set": updates})
        # Create spec from template features
        if tpl.get("features_template"):
            spec = {
                "spec_id": f"spec_{uuid.uuid4().hex[:12]}",
                "idea_id": idea_id,
                "title": f"{tpl['name']} Spec",
                "features": tpl["features_template"],
                "user_stories": [],
                "tech_requirements": [],
                "constraints": [],
                "created_by": "template",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.feature_specs.insert_one(spec)
        await db.idea_templates.update_one({"template_id": template_id}, {"$inc": {"uses": 1}})
        return {"applied": True, "template": tpl["name"]}
