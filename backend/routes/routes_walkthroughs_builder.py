from nexus_utils import now_iso
"""Walkthrough Builder API — CRUD, SDK endpoints, analytics, progress tracking"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


# ============ Models ============

class StepContent(BaseModel):
    title: str = ""
    body: str = ""
    media: Optional[dict] = None
    cta_label: str = "Next"
    cta_style: str = "primary"
    dismissible: bool = True
    show_progress: bool = True

class StepBehavior(BaseModel):
    advance_on: str = "click_cta"  # click_cta, click_element, delay, navigation
    advance_config: dict = {}
    placement: str = "bottom"  # top, bottom, left, right, auto
    highlight_padding: int = 8
    scroll_to: bool = True
    wait_for_element: bool = True
    wait_timeout: int = 5000

class StepCreate(BaseModel):
    step_type: str = "tooltip"  # tooltip, modal, spotlight, action, beacon, checklist
    selector_primary: str = ""
    selector_css: str = ""
    selector_text: Optional[str] = None
    content: StepContent = StepContent()
    behavior: StepBehavior = StepBehavior()
    branching: Optional[dict] = None  # {condition: {type, property, operator, value}, then_step_id, else_step_id}
    checklist_items: Optional[List[dict]] = None  # For checklist type: [{id, label, walkthrough_id}]

class WalkthroughCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    category: str = "onboarding"

class WalkthroughUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_url_pattern: Optional[str] = None
    trigger_event: Optional[str] = None
    frequency_rule: Optional[str] = None
    frequency_interval_days: Optional[int] = None
    targeting_audiences: Optional[List[dict]] = None
    theme: Optional[dict] = None

class EventBatch(BaseModel):
    events: List[dict]

VALID_STEP_TYPES = ["tooltip", "modal", "spotlight", "action", "beacon", "checklist"]
VALID_STATUSES = ["draft", "published", "archived"]
VALID_CATEGORIES = ["onboarding", "feature", "setup", "announcement", "custom"]
VALID_TRIGGERS = ["page_load", "first_visit", "event", "manual", "scheduled"]
VALID_FREQUENCIES = ["once", "until_completed", "every_n_days", "always"]

# Permissions matrix
WALKTHROUGH_PERMISSIONS = {
    "super_admin": {"create": True, "edit_own": True, "edit_all": True, "publish": True, "delete": True, "view_analytics": "all"},
    "admin": {"create": True, "edit_own": True, "edit_all": True, "publish": True, "delete": False, "view_analytics": "all"},
    "moderator": {"create": True, "edit_own": True, "edit_all": False, "publish": False, "delete": False, "view_analytics": "own"},
    "user": {"create": False, "edit_own": False, "edit_all": False, "publish": False, "delete": False, "view_analytics": False},
}



def register_walkthrough_routes(api_router, db, get_current_user):

    def check_permission(user, action):
        role = user.get("platform_role", "user")
        perms = WALKTHROUGH_PERMISSIONS.get(role, WALKTHROUGH_PERMISSIONS["user"])
        return perms.get(action, False)

    # ============ Config (MUST be before /:id routes) ============

    @api_router.get("/walkthroughs/config")
    async def get_walkthrough_config(request: Request):
        user = await get_current_user(request)
        role = user.get("platform_role", "user")
        return {
            "step_types": VALID_STEP_TYPES,
            "categories": VALID_CATEGORIES,
            "trigger_types": VALID_TRIGGERS,
            "frequency_rules": VALID_FREQUENCIES,
            "advance_conditions": ["click_cta", "click_element", "delay", "navigation", "custom_event"],
            "placements": ["top", "bottom", "left", "right", "auto"],
            "branching_operators": ["eq", "neq", "contains", "gt", "lt"],
            "branching_condition_types": ["user_property", "step_action", "element_state"],
            "permissions": WALKTHROUGH_PERMISSIONS.get(role, WALKTHROUGH_PERMISSIONS["user"]),
        }

    # ============ Walkthrough CRUD ============

    @api_router.post("/walkthroughs")
    async def create_walkthrough(data: WalkthroughCreate, request: Request):
        user = await get_current_user(request)
        wt_id = f"wt_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        walkthrough = {
            "walkthrough_id": wt_id,
            "name": data.name,
            "description": data.description,
            "category": data.category if data.category in VALID_CATEGORIES else "custom",
            "status": "draft",
            "version": 0,
            "steps": [],
            "trigger": {"type": "page_load", "url_pattern": None, "event_name": None, "schedule": None},
            "targeting": {"audiences": []},
            "frequency": {"rule": "once", "interval_days": None, "max_per_session": 3},
            "theme": {
                "primary_color": "#10B981",
                "background_color": "#18181b",
                "text_color": "#fafafa",
                "border_radius": 12,
                "font_family": None,
                "overlay_color": "rgba(0,0,0,0.6)",
                "overlay_blur": 4,
                "z_index": 10000,
            },
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "published_at": None,
        }
        await db.walkthroughs.insert_one(walkthrough)
        return {k: v for k, v in walkthrough.items() if k != "_id"}

    @api_router.get("/walkthroughs")
    async def list_walkthroughs(request: Request, status: Optional[str] = None, category: Optional[str] = None):
        await get_current_user(request)
        query = {}
        if status and status in VALID_STATUSES:
            query["status"] = status
        if category:
            query["category"] = category
        items = await db.walkthroughs.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
        return {"walkthroughs": items, "total": len(items)}

    @api_router.get("/walkthroughs/{wt_id}")
    async def get_walkthrough(wt_id: str, request: Request):
        await get_current_user(request)
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")
        return wt

    @api_router.put("/walkthroughs/{wt_id}")
    async def update_walkthrough(wt_id: str, data: WalkthroughUpdate, request: Request):
        await get_current_user(request)
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")
        updates = {"updated_at": now_iso()}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.category is not None:
            updates["category"] = data.category
        if data.trigger_type is not None:
            updates["trigger.type"] = data.trigger_type
        if data.trigger_url_pattern is not None:
            updates["trigger.url_pattern"] = data.trigger_url_pattern
        if data.trigger_event is not None:
            updates["trigger.event_name"] = data.trigger_event
        if data.frequency_rule is not None:
            updates["frequency.rule"] = data.frequency_rule
        if data.frequency_interval_days is not None:
            updates["frequency.interval_days"] = data.frequency_interval_days
        if data.targeting_audiences is not None:
            updates["targeting.audiences"] = data.targeting_audiences
        if data.theme is not None:
            updates["theme"] = data.theme
        await db.walkthroughs.update_one({"walkthrough_id": wt_id}, {"$set": updates})
        return await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})

    @api_router.delete("/walkthroughs/{wt_id}")
    async def delete_walkthrough(wt_id: str, request: Request):
        await get_current_user(request)
        result = await db.walkthroughs.delete_one({"walkthrough_id": wt_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Walkthrough not found")
        await db.walkthrough_progress.delete_many({"walkthrough_id": wt_id})
        await db.walkthrough_events.delete_many({"walkthrough_id": wt_id})
        await db.walkthrough_versions.delete_many({"walkthrough_id": wt_id})
        return {"message": "Deleted"}

    # ============ Steps CRUD ============

    @api_router.post("/walkthroughs/{wt_id}/steps")
    async def add_step(wt_id: str, data: StepCreate, request: Request):
        await get_current_user(request)
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")
        step_id = f"ws_{uuid.uuid4().hex[:12]}"
        step = {
            "step_id": step_id,
            "type": data.step_type if data.step_type in VALID_STEP_TYPES else "tooltip",
            "order": len(wt.get("steps") or []),
            "selector": {
                "primary": data.selector_primary,
                "css": data.selector_css,
                "text_content": data.selector_text,
                "resilience": "high" if data.selector_primary else ("medium" if data.selector_css else "low"),
            },
            "content": data.content.dict(),
            "behavior": data.behavior.dict(),
            "branching": data.branching,
            "checklist_items": data.checklist_items if data.step_type == "checklist" else None,
        }
        await db.walkthroughs.update_one(
            {"walkthrough_id": wt_id},
            {"$push": {"steps": step}, "$set": {"updated_at": now_iso()}}
        )
        return step

    @api_router.put("/walkthroughs/{wt_id}/steps/{step_id}")
    async def update_step(wt_id: str, step_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")
        steps = wt.get("steps") or []
        found = False
        for i, s in enumerate(steps):
            if s["step_id"] == step_id:
                for key in ["type", "selector", "content", "behavior"]:
                    if key in body:
                        steps[i][key] = body[key]
                found = True
                break
        if not found:
            raise HTTPException(404, "Step not found")
        await db.walkthroughs.update_one(
            {"walkthrough_id": wt_id},
            {"$set": {"steps": steps, "updated_at": now_iso()}}
        )
        return steps[[s["step_id"] for s in steps].index(step_id)]

    @api_router.delete("/walkthroughs/{wt_id}/steps/{step_id}")
    async def delete_step(wt_id: str, step_id: str, request: Request):
        await get_current_user(request)
        result = await db.walkthroughs.update_one(
            {"walkthrough_id": wt_id},
            {"$pull": {"steps": {"step_id": step_id}}, "$set": {"updated_at": now_iso()}}
        )
        if result.modified_count == 0:
            raise HTTPException(404, "Step not found")
        # Reorder remaining steps
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if wt:
            steps = wt.get("steps") or []
            for i, s in enumerate(steps):
                s["order"] = i
            await db.walkthroughs.update_one({"walkthrough_id": wt_id}, {"$set": {"steps": steps}})
        return {"message": "Step deleted"}

    @api_router.put("/walkthroughs/{wt_id}/steps/reorder")
    async def reorder_steps(wt_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        step_ids = body.get("step_ids") or []
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")
        step_map = {s["step_id"]: s for s in wt.get("steps") or []}
        reordered = []
        for i, sid in enumerate(step_ids):
            if sid in step_map:
                step_map[sid]["order"] = i
                reordered.append(step_map[sid])
        await db.walkthroughs.update_one({"walkthrough_id": wt_id}, {"$set": {"steps": reordered, "updated_at": now_iso()}})
        return {"steps": reordered}

    # ============ Publish / Archive / Version ============

    @api_router.post("/walkthroughs/{wt_id}/publish")
    async def publish_walkthrough(wt_id: str, request: Request):
        user = await get_current_user(request)
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")
        if not wt.get("steps"):
            raise HTTPException(400, "Cannot publish walkthrough with no steps")
        new_version = wt.get("version", 0) + 1
        now = now_iso()
        await db.walkthroughs.update_one(
            {"walkthrough_id": wt_id},
            {"$set": {"status": "published", "version": new_version, "published_at": now, "updated_at": now}}
        )
        # Save version snapshot
        await db.walkthrough_versions.insert_one({
            "version_id": f"wtv_{uuid.uuid4().hex[:8]}",
            "walkthrough_id": wt_id,
            "version_number": new_version,
            "snapshot": wt,
            "published_by": user["user_id"],
            "published_at": now,
        })
        return await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})

    @api_router.post("/walkthroughs/{wt_id}/archive")
    async def archive_walkthrough(wt_id: str, request: Request):
        await get_current_user(request)
        await db.walkthroughs.update_one(
            {"walkthrough_id": wt_id},
            {"$set": {"status": "archived", "updated_at": now_iso()}}
        )
        return await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})

    @api_router.get("/walkthroughs/{wt_id}/versions")
    async def list_versions(wt_id: str, request: Request):
        await get_current_user(request)
        versions = await db.walkthrough_versions.find(
            {"walkthrough_id": wt_id}, {"_id": 0}
        ).sort("version_number", -1).to_list(20)
        return versions

    @api_router.post("/walkthroughs/{wt_id}/rollback/{version}")
    async def rollback_version(wt_id: str, version: int, request: Request):
        await get_current_user(request)
        ver = await db.walkthrough_versions.find_one(
            {"walkthrough_id": wt_id, "version_number": version}, {"_id": 0}
        )
        if not ver:
            raise HTTPException(404, f"Version {version} not found")
        snapshot = ver["snapshot"]
        await db.walkthroughs.update_one(
            {"walkthrough_id": wt_id},
            {"$set": {
                "steps": snapshot.get("steps") or [],
                "trigger": snapshot.get("trigger") or {},
                "targeting": snapshot.get("targeting") or {},
                "frequency": snapshot.get("frequency") or {},
                "theme": snapshot.get("theme") or {},
                "status": "draft",
                "updated_at": now_iso(),
            }}
        )
        return await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})

    # ============ SDK Endpoints ============

    @api_router.get("/sdk/walkthroughs/active")
    async def get_active_walkthroughs(request: Request, url: str = "", userId: str = ""):
        """SDK endpoint — returns published walkthroughs matching the current context"""
        # This is a high-traffic read endpoint — no auth required (SDK calls it)
        query = {"status": "published"}
        walkthroughs = await db.walkthroughs.find(query, {"_id": 0}).to_list(50)

        # Filter by URL pattern if provided
        active = []
        for wt in walkthroughs:
            trigger = wt.get("trigger") or {}
            url_pattern = trigger.get("url_pattern")
            if url_pattern and url:
                import fnmatch
                if not fnmatch.fnmatch(url, url_pattern):
                    continue
            active.append(wt)

        # Get user progress
        progress = []
        if userId:
            progress = await db.walkthrough_progress.find(
                {"user_id": userId}, {"_id": 0}
            ).to_list(50)

        return {"walkthroughs": active, "user_progress": progress}

    @api_router.post("/sdk/events")
    async def ingest_events(data: EventBatch, request: Request):
        """SDK endpoint — batch ingest walkthrough events"""
        if not data.events:
            return {"accepted": 0}
        docs = []
        for evt in data.events[:50]:  # Max 50 per batch
            docs.append({
                "event_id": evt.get("id", f"we_{uuid.uuid4().hex[:8]}"),
                "walkthrough_id": evt.get("walkthroughId", ""),
                "step_id": evt.get("stepId"),
                "user_id": evt.get("userId", ""),
                "event_type": evt.get("eventType", "unknown"),
                "metadata": evt.get("metadata") or {},
                "timestamp": evt.get("timestamp", now_iso()),
            })
        if docs:
            await db.walkthrough_events.insert_many(docs)
        return {"accepted": len(docs)}

    @api_router.post("/sdk/progress")
    async def update_progress(request: Request):
        """SDK endpoint — update user progress on a walkthrough"""
        body = await request.json()
        user_id = body.get("userId", "")
        wt_id = body.get("walkthroughId", "")
        step_id = body.get("currentStepId")
        status = body.get("status", "in_progress")
        if not user_id or not wt_id:
            raise HTTPException(400, "userId and walkthroughId required")
        now = now_iso()
        updates = {"current_step_id": step_id, "status": status, "last_seen_at": now}
        if status == "in_progress" and not await db.walkthrough_progress.find_one({"user_id": user_id, "walkthrough_id": wt_id}):
            updates["started_at"] = now
        if status == "completed":
            updates["completed_at"] = now
        await db.walkthrough_progress.update_one(
            {"user_id": user_id, "walkthrough_id": wt_id},
            {"$set": updates, "$setOnInsert": {"user_id": user_id, "walkthrough_id": wt_id}},
            upsert=True
        )
        return {"status": "updated"}

    # ============ Analytics ============

    @api_router.get("/walkthroughs/{wt_id}/analytics")
    async def get_walkthrough_analytics(wt_id: str, request: Request):
        await get_current_user(request)
        # Summary
        total_starts = await db.walkthrough_events.count_documents({"walkthrough_id": wt_id, "event_type": "started"})
        total_completions = await db.walkthrough_events.count_documents({"walkthrough_id": wt_id, "event_type": "completed"})
        total_dismissed = await db.walkthrough_events.count_documents({"walkthrough_id": wt_id, "event_type": "dismissed"})

        completion_rate = round(total_completions / max(total_starts, 1), 3)

        # Step funnel
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        funnel = []
        if wt:
            for step in wt.get("steps") or []:
                sid = step["step_id"]
                viewed = await db.walkthrough_events.count_documents({"walkthrough_id": wt_id, "step_id": sid, "event_type": "step_viewed"})
                completed = await db.walkthrough_events.count_documents({"walkthrough_id": wt_id, "step_id": sid, "event_type": "step_completed"})
                funnel.append({
                    "step_id": sid,
                    "step_order": step["order"],
                    "step_type": step["type"],
                    "title": (step.get("content") or {}).get("title", ""),
                    "viewed": viewed,
                    "completed": completed,
                    "drop_off_rate": round(1 - (completed / max(viewed, 1)), 3),
                })

        return {
            "summary": {
                "total_starts": total_starts,
                "total_completions": total_completions,
                "total_dismissed": total_dismissed,
                "completion_rate": completion_rate,
            },
            "funnel": funnel,
        }

    # ============ Config (duplicate removed — defined above CRUD routes) ============

    # ============ Resource Center ============

    @api_router.get("/sdk/resource-center")
    async def get_resource_center(request: Request, userId: str = ""):
        """SDK endpoint — resource center with categorized walkthroughs and progress"""
        walkthroughs = await db.walkthroughs.find(
            {"status": "published"}, {"_id": 0, "walkthrough_id": 1, "name": 1, "description": 1, "category": 1, "steps": 1}
        ).to_list(50)

        progress_map = {}
        if userId:
            progress_list = await db.walkthrough_progress.find({"user_id": userId}, {"_id": 0}).to_list(50)
            progress_map = {p["walkthrough_id"]: p for p in progress_list}

        items = []
        for wt in walkthroughs:
            prog = progress_map.get(wt["walkthrough_id"], {})
            items.append({
                "walkthrough_id": wt["walkthrough_id"],
                "name": wt["name"],
                "description": wt.get("description", ""),
                "category": wt.get("category", "custom"),
                "step_count": len(wt.get("steps") or []),
                "status": prog.get("status", "not_started"),
                "completed": prog.get("status") == "completed",
            })

        # Group by category
        categories = {}
        for item in items:
            cat = item["category"]
            categories.setdefault(cat, []).append(item)

        total = len(items)
        completed = sum(1 for i in items if i["completed"])

        return {
            "categories": categories,
            "total_walkthroughs": total,
            "completed": completed,
            "progress_pct": round(completed / max(total, 1) * 100),
        }

    # ============ Branching Validation ============

    @api_router.post("/walkthroughs/{wt_id}/validate")
    async def validate_walkthrough(wt_id: str, request: Request):
        """Validate walkthrough for issues before publishing"""
        await get_current_user(request)
        wt = await db.walkthroughs.find_one({"walkthrough_id": wt_id}, {"_id": 0})
        if not wt:
            raise HTTPException(404, "Walkthrough not found")

        issues = []
        steps = wt.get("steps") or []
        step_ids = {s["step_id"] for s in steps}

        if not steps:
            issues.append({"level": "error", "message": "Walkthrough has no steps"})

        for step in steps:
            # Check selector
            sel = step.get("selector") or {}
            if not sel.get("primary") and not sel.get("css"):
                if step["type"] not in ("modal", "checklist"):
                    issues.append({"level": "warning", "message": f"Step '{step.get('content', {}).get('title', step['step_id'])}' has no target selector", "step_id": step["step_id"]})

            # Check branching references
            branching = step.get("branching")
            if branching:
                then_id = branching.get("then_step_id")
                else_id = branching.get("else_step_id")
                if then_id and then_id not in step_ids:
                    issues.append({"level": "error", "message": f"Branching target step '{then_id}' not found", "step_id": step["step_id"]})
                if else_id and else_id not in step_ids:
                    issues.append({"level": "error", "message": f"Branching else step '{else_id}' not found", "step_id": step["step_id"]})

            # Check checklist items
            if step["type"] == "checklist" and not step.get("checklist_items"):
                issues.append({"level": "warning", "message": "Checklist step has no items", "step_id": step["step_id"]})

        has_errors = any(i["level"] == "error" for i in issues)
        return {"valid": not has_errors, "issues": issues}
