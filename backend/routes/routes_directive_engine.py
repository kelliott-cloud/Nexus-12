"""Directive Engine — Structured directives as runtime constraints on AI agents"""
import uuid
import logging
import re
import io
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request, UploadFile, File
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



class DirectiveCreate(BaseModel):
    project_name: str = Field(..., min_length=1)
    description: str = ""
    agents: dict = {}  # {agent_key: {display_name, model, prompt_constraints[], max_retries, token_budget_per_task}}
    universal_rules: dict = {}  # {full_file_context, additive_only, max_retries, require_dual_review, prohibited_patterns[]}
    phases: list = []  # [{name, gate, tasks: [{title, description, assigned_agent, target_file, acceptance_criteria[]}]}]
    cost_controls: dict = {}


def register_directive_engine_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ===== Directive CRUD =====

    @api_router.post("/workspaces/{workspace_id}/directives")
    async def create_directive(workspace_id: str, data: DirectiveCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        now = now_iso()
        directive_id = f"dir_{uuid.uuid4().hex[:12]}"

        directive = {
            "directive_id": directive_id,
            "workspace_id": workspace_id,
            "project_name": data.project_name,
            "description": data.description,
            "agents": data.agents,
            "universal_rules": {
                "full_file_context": data.universal_rules.get("full_file_context", True),
                "additive_only": data.universal_rules.get("additive_only", True),
                "max_retries_on_validation_fail": data.universal_rules.get("max_retries", 3),
                "require_dual_review": data.universal_rules.get("require_dual_review", False),
                "prohibited_patterns": data.universal_rules.get("prohibited_patterns") or [],
                "max_parallel_tasks": data.universal_rules.get("max_parallel_tasks", 5),
            },
            "phases": data.phases,
            "cost_controls": {
                "global_token_budget": data.cost_controls.get("global_token_budget", 5000000),
                "per_task_token_limit": data.cost_controls.get("per_task_token_limit", 200000),
                "alert_at_percentage": data.cost_controls.get("alert_at_percentage", 80),
            },
            "is_active": False,
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.directives.insert_one(directive)
        return {k: v for k, v in directive.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/directives")
    async def list_directives(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        directives = await db.directives.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return {"directives": directives}

    @api_router.get("/workspaces/{workspace_id}/directives/active")
    async def get_active_directive(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        directive = await db.directives.find_one(
            {"workspace_id": workspace_id, "is_active": True}, {"_id": 0}
        )
        if not directive:
            return {"directive": None}
        # Get task counts
        total = await db.directive_tasks.count_documents({"directive_id": directive["directive_id"]})
        done = await db.directive_tasks.count_documents({"directive_id": directive["directive_id"], "status": "merged"})
        directive["task_count"] = total
        directive["tasks_done"] = done
        return {"directive": directive}

    @api_router.get("/directives/{directive_id}")
    async def get_directive(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        directive = await db.directives.find_one({"directive_id": directive_id}, {"_id": 0})
        if not directive:
            raise HTTPException(404, "Directive not found")
        return directive

    @api_router.put("/directives/{directive_id}/activate")
    async def activate_directive(directive_id: str, request: Request):
        """Activate directive and auto-generate tasks from phases"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        directive = await db.directives.find_one({"directive_id": directive_id})
        if not directive:
            raise HTTPException(404, "Directive not found")

        now = now_iso()
        ws_id = directive["workspace_id"]

        # Deactivate any existing active directive
        await db.directives.update_many(
            {"workspace_id": ws_id, "is_active": True},
            {"$set": {"is_active": False, "updated_at": now}}
        )

        # Activate this one
        await db.directives.update_one(
            {"directive_id": directive_id},
            {"$set": {"is_active": True, "activated_at": now, "updated_at": now}}
        )

        # Auto-generate tasks from phases
        task_count = 0
        for phase_idx, phase in enumerate(directive.get("phases") or []):
            phase_id = f"phase_{phase_idx}"
            for task_def in phase.get("tasks") or []:
                task_id = f"dtask_{uuid.uuid4().hex[:12]}"
                await db.directive_tasks.insert_one({
                    "task_id": task_id,
                    "directive_id": directive_id,
                    "workspace_id": ws_id,
                    "phase_id": phase_id,
                    "phase_name": phase.get("name", f"Phase {phase_idx}"),
                    "phase_gate": phase.get("gate", ""),
                    "title": task_def.get("title", ""),
                    "description": task_def.get("description", ""),
                    "assigned_agent": task_def.get("assigned_agent", ""),
                    "target_file": task_def.get("target_file", ""),
                    "acceptance_criteria": task_def.get("acceptance_criteria") or [],
                    "depends_on": task_def.get("depends_on") or [],
                    "status": "ready" if phase_idx == 0 else "todo",
                    "retries": 0,
                    "max_retries": (directive.get("universal_rules") or {}).get("max_retries_on_validation_fail", 3),
                    "created_at": now,
                    "completed_at": None,
                })
                task_count += 1

                # Create file ownership if target_file specified
                if task_def.get("target_file"):
                    existing = await db.directive_file_ownership.find_one({
                        "directive_id": directive_id, "file_path": task_def["target_file"]
                    })
                    if not existing:
                        await db.directive_file_ownership.insert_one({
                            "ownership_id": f"own_{uuid.uuid4().hex[:12]}",
                            "directive_id": directive_id,
                            "file_path": task_def["target_file"],
                            "owner": task_def.get("assigned_agent", ""),
                            "reviewers": task_def.get("reviewers") or [],
                            "locked": False,
                            "protected_methods": task_def.get("protected_methods") or [],
                            "protected_attributes": task_def.get("protected_attributes") or [],
                        })

        # Audit
        await db.directive_audit_events.insert_one({
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "workspace_id": ws_id,
            "event_type": "directive_activated",
            "directive_id": directive_id,
            "payload": {"task_count": task_count, "phase_count": len(directive.get("phases") or [])},
            "timestamp": now,
        })

        return {"activated": True, "tasks_created": task_count}

    @api_router.put("/directives/{directive_id}/deactivate")
    async def deactivate_directive(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        await db.directives.update_one(
            {"directive_id": directive_id},
            {"$set": {"is_active": False, "updated_at": now_iso()}}
        )
        return {"deactivated": True}

    # ===== Directive Tasks =====

    @api_router.get("/directives/{directive_id}/tasks")
    async def list_directive_tasks(directive_id: str, request: Request, phase_id: str = None, status: str = None):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        query = {"directive_id": directive_id}
        if phase_id:
            query["phase_id"] = phase_id
        if status:
            query["status"] = status
        tasks = await db.directive_tasks.find(query, {"_id": 0}).sort("created_at", 1).to_list(500)
        return {"tasks": tasks}

    @api_router.get("/directives/{directive_id}/phases")
    async def list_phases(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        directive = await db.directives.find_one({"directive_id": directive_id}, {"_id": 0, "phases": 1})
        if not directive:
            raise HTTPException(404, "Directive not found")
        phases = []
        for i, phase in enumerate(directive.get("phases") or []):
            phase_id = f"phase_{i}"
            total = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": phase_id})
            done = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": phase_id, "status": "merged"})
            phases.append({
                "phase_id": phase_id,
                "name": phase.get("name", f"Phase {i}"),
                "gate": phase.get("gate", ""),
                "total_tasks": total,
                "done_tasks": done,
                "progress": round(done / total * 100) if total > 0 else 0,
            })
        return {"phases": phases}

    @api_router.put("/directive-tasks/{task_id}/status")
    async def update_directive_task_status(task_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        new_status = body.get("status", "")
        if new_status not in ("todo", "ready", "assigned", "in_progress", "validation", "review", "merged", "failed", "escalated"):
            raise HTTPException(400, "Invalid status")
        updates = {"status": new_status, "updated_at": now_iso()}
        if new_status == "merged":
            updates["completed_at"] = now_iso()
        await db.directive_tasks.update_one({"task_id": task_id}, {"$set": updates})
        return {"updated": True, "status": new_status}

    # ===== File Ownership =====

    @api_router.get("/directives/{directive_id}/ownership")
    async def list_ownership(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        ownership = await db.directive_file_ownership.find(
            {"directive_id": directive_id}, {"_id": 0}
        ).to_list(200)
        return {"ownership": ownership}

    # ===== Audit Events =====

    @api_router.get("/directives/{directive_id}/audit")
    async def list_audit_events(directive_id: str, request: Request, limit: int = 50):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        events = await db.directive_audit_events.find(
            {"directive_id": directive_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"events": events}

    # ===== Metrics =====

    @api_router.get("/directives/{directive_id}/metrics")
    async def get_directive_metrics(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        total = await db.directive_tasks.count_documents({"directive_id": directive_id})
        by_status = {}
        for s in ["todo", "ready", "in_progress", "validation", "review", "merged", "failed", "escalated"]:
            by_status[s] = await db.directive_tasks.count_documents({"directive_id": directive_id, "status": s})
        done = by_status.get("merged", 0)
        return {
            "total_tasks": total,
            "tasks_by_status": by_status,
            "progress": round(done / total * 100) if total > 0 else 0,
            "completed": done,
        }

    # ===== Channel-Level Directive (the popup flow) =====

    @api_router.get("/channels/{channel_id}/directive")
    async def get_channel_directive(channel_id: str, request: Request):
        """Get the active directive for a channel's workspace"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_channel_access
        await require_channel_access(db, user, channel_id)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
        if not channel:
            raise HTTPException(404, "Channel not found")
        directive = await db.directives.find_one(
            {"workspace_id": channel["workspace_id"], "is_active": True}, {"_id": 0}
        )
        return {"directive": directive}

    @api_router.post("/channels/{channel_id}/directive")
    async def create_channel_directive(channel_id: str, request: Request):
        """Quick-create a directive from the channel interface"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_channel_access
        await require_channel_access(db, user, channel_id)
        body = await request.json()
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")

        ws_id = channel["workspace_id"]
        now = now_iso()
        directive_id = f"dir_{uuid.uuid4().hex[:12]}"

        # Build agent configs from channel agents
        agents = {}
        for agent_key in channel.get("ai_agents") or []:
            agent_config = (body.get("agents") or {}).get(agent_key, {})
            agents[agent_key] = {
                "display_name": agent_config.get("display_name", agent_key),
                "role": agent_config.get("role", "contributor"),
                "prompt_constraints": agent_config.get("prompt_constraints") or [],
                "max_retries": agent_config.get("max_retries", 3),
            }

        directive = {
            "directive_id": directive_id,
            "workspace_id": ws_id,
            "channel_id": channel_id,
            "project_name": body.get("project_name", channel.get("name", "Untitled")),
            "description": body.get("description", ""),
            "goal": body.get("goal", ""),
            "agents": agents,
            "universal_rules": body.get("universal_rules", {
                "full_file_context": True,
                "additive_only": True,
                "max_retries_on_validation_fail": 3,
                "prohibited_patterns": [],
                "max_parallel_tasks": 5,
            }),
            "phases": body.get("phases") or [],
            "cost_controls": body.get("cost_controls") or {},
            "is_active": True,
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "activated_at": now,
        }

        # Deactivate existing
        await db.directives.update_many(
            {"workspace_id": ws_id, "is_active": True},
            {"$set": {"is_active": False}}
        )
        await db.directives.insert_one(directive)

        # Auto-generate tasks if phases provided
        task_count = 0
        for phase_idx, phase in enumerate(body.get("phases") or []):
            phase_id = f"phase_{phase_idx}"
            for task_def in phase.get("tasks") or []:
                task_id = f"dtask_{uuid.uuid4().hex[:12]}"
                await db.directive_tasks.insert_one({
                    "task_id": task_id,
                    "directive_id": directive_id,
                    "workspace_id": ws_id,
                    "phase_id": phase_id,
                    "phase_name": phase.get("name", f"Phase {phase_idx}"),
                    "title": task_def.get("title", ""),
                    "description": task_def.get("description", ""),
                    "assigned_agent": task_def.get("assigned_agent", ""),
                    "target_file": task_def.get("target_file", ""),
                    "acceptance_criteria": task_def.get("acceptance_criteria") or [],
                    "status": "ready" if phase_idx == 0 else "todo",
                    "retries": 0,
                    "created_at": now,
                })
                task_count += 1

        return {k: v for k, v in directive.items() if k != "_id" and k != "task_count"}

    @api_router.put("/channels/{channel_id}/directive")
    async def update_channel_directive(channel_id: str, request: Request):
        """Update an existing active directive from the channel interface"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_channel_access
        await require_channel_access(db, user, channel_id)
        body = await request.json()
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")

        ws_id = channel["workspace_id"]
        existing = await db.directives.find_one(
            {"workspace_id": ws_id, "is_active": True}, {"_id": 0}
        )
        if not existing:
            raise HTTPException(404, "No active directive to edit")

        now = now_iso()
        updates = {"updated_at": now}

        if "project_name" in body:
            updates["project_name"] = body["project_name"]
        if "description" in body:
            updates["description"] = body["description"]
        if "goal" in body:
            updates["goal"] = body["goal"]
        if "agents" in body:
            agents = {}
            for agent_key, agent_config in body["agents"].items():
                agents[agent_key] = {
                    "display_name": agent_config.get("display_name", agent_key),
                    "role": agent_config.get("role", "contributor"),
                    "prompt_constraints": agent_config.get("prompt_constraints") or [],
                    "max_retries": agent_config.get("max_retries", 3),
                }
            updates["agents"] = agents
        if "universal_rules" in body:
            updates["universal_rules"] = body["universal_rules"]
        if "phases" in body:
            updates["phases"] = body["phases"]

        await db.directives.update_one(
            {"directive_id": existing["directive_id"]},
            {"$set": updates}
        )

        updated = await db.directives.find_one(
            {"directive_id": existing["directive_id"]}, {"_id": 0}
        )
        return updated


    # ===== File Upload & Parse =====

    @api_router.post("/directives/upload-document")
    async def upload_directive_document(request: Request, file: UploadFile = File(...)):
        """Upload a text/docx/pdf file and extract its content for directive context"""
        await get_current_user(request)
        
        filename = file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        content_bytes = await file.read()
        
        if len(content_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(400, "File too large (max 10MB)")
        
        extracted_text = ""
        
        if ext == "txt" or ext == "md":
            extracted_text = content_bytes.decode("utf-8", errors="replace")
        
        elif ext == "pdf":
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content_bytes))
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                extracted_text = "\n\n".join(pages)
            except Exception as e:
                raise HTTPException(400, f"Failed to parse PDF: {str(e)[:200]}")
        
        elif ext in ("docx", "doc"):
            try:
                from docx import Document
                doc = Document(io.BytesIO(content_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                extracted_text = "\n\n".join(paragraphs)
            except Exception as e:
                raise HTTPException(400, f"Failed to parse DOCX: {str(e)[:200]}")
        
        else:
            raise HTTPException(400, f"Unsupported file type: .{ext}. Supported: .txt, .md, .pdf, .docx")
        
        if not extracted_text.strip():
            raise HTTPException(400, "No text content could be extracted from the file")
        
        # Store the document for reference
        doc_id = f"ddoc_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        await db.directive_documents.insert_one({
            "doc_id": doc_id,
            "filename": filename,
            "file_type": ext,
            "content": extracted_text[:500000],  # Cap at 500K chars
            "char_count": len(extracted_text),
            "uploaded_at": now,
        })
        
        return {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": ext,
            "char_count": len(extracted_text),
            "preview": extracted_text[:1000],
            "content": extracted_text[:100000],  # Return up to 100K for immediate use
        }

    @api_router.get("/directive-documents/{doc_id}")
    async def get_directive_document(doc_id: str, request: Request):
        await get_current_user(request)
        doc = await db.directive_documents.find_one({"doc_id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Document not found")
        return doc



    # ===== Validation Pipeline =====

    @api_router.post("/directive-tasks/{task_id}/validate")
    async def validate_directive_task(task_id: str, request: Request):
        """Validate task output against acceptance criteria"""
        user = await get_current_user(request)
        task = await db.directive_tasks.find_one({"task_id": task_id}, {"_id": 0})
        if not task:
            raise HTTPException(404, "Task not found")
        
        body = await request.json()
        output = body.get("output", "")
        criteria = task.get("acceptance_criteria") or []
        now = now_iso()
        
        # Check each criterion
        results = []
        all_passed = True
        for criterion in criteria:
            # Simple keyword/pattern check
            passed = criterion.lower() in output.lower() if criterion else True
            results.append({"criterion": criterion, "passed": passed})
            if not passed:
                all_passed = False
        
        # Check prohibited patterns from directive
        directive = await db.directives.find_one({"directive_id": task.get("directive_id")}, {"_id": 0})
        prohibited = (directive.get("universal_rules") or {}).get("prohibited_patterns") or [] if directive else []
        for pattern in prohibited:
            if pattern.lower() in output.lower():
                results.append({"criterion": f"No '{pattern}'", "passed": False})
                all_passed = False
        
        if all_passed:
            await db.directive_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "review", "validated_at": now, "validation_results": results}}
            )
        else:
            retries = task.get("retries", 0) + 1
            max_retries = task.get("max_retries", 3)
            if retries >= max_retries:
                await db.directive_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"status": "escalated", "retries": retries, "validation_results": results}}
                )
                # Create escalation notification
                await db.notifications.insert_one({
                    "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                    "user_id": task.get("created_by", user["user_id"]),
                    "type": "task_escalated",
                    "title": f"Task escalated: {task.get('title', '')}",
                    "message": f"Task failed validation {retries} times and needs human review.",
                    "read": False,
                    "created_at": now,
                })
            else:
                await db.directive_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"status": "in_progress", "retries": retries, "validation_results": results}}
                )
        
        await db.directive_audit_events.insert_one({
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "event_type": "task_validated",
            "directive_id": task.get("directive_id"),
            "payload": {"task_id": task_id, "passed": all_passed, "retries": task.get("retries", 0), "results": results},
            "timestamp": now,
        })
        
        return {"passed": all_passed, "results": results, "status": "review" if all_passed else ("escalated" if task.get("retries", 0) + 1 >= task.get("max_retries", 3) else "retry")}

    # ===== Phase Gates =====

    @api_router.post("/directives/{directive_id}/check-gate/{phase_id}")
    async def check_phase_gate(directive_id: str, phase_id: str, request: Request):
        """Check if a phase gate is satisfied to unlock next phase"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        
        total = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": phase_id})
        merged = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": phase_id, "status": "merged"})
        failed = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": phase_id, "status": {"$in": ["failed", "escalated"]}})
        
        gate_passed = total > 0 and merged == total
        
        if gate_passed:
            # Unlock next phase tasks
            phase_num = int(phase_id.split("_")[1]) if "_" in phase_id else 0
            next_phase = f"phase_{phase_num + 1}"
            result = await db.directive_tasks.update_many(
                {"directive_id": directive_id, "phase_id": next_phase, "status": "todo"},
                {"$set": {"status": "ready"}}
            )
            await db.directive_audit_events.insert_one({
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "event_type": "phase_gate_passed",
                "directive_id": directive_id,
                "payload": {"phase_id": phase_id, "next_phase": next_phase, "tasks_unlocked": result.modified_count},
                "timestamp": now_iso(),
            })
        
        return {
            "gate_passed": gate_passed,
            "total": total, "merged": merged, "failed": failed,
            "remaining": total - merged - failed,
        }

    # ===== Cost Tracking =====

    @api_router.post("/directives/{directive_id}/track-cost")
    async def track_cost(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        body = await request.json()
        task_id = body.get("task_id", "")
        tokens_used = body.get("tokens_used", 0)
        agent_key = body.get("agent_key", "")
        
        now = now_iso()
        await db.directive_cost_tracking.insert_one({
            "tracking_id": f"cost_{uuid.uuid4().hex[:12]}",
            "directive_id": directive_id,
            "task_id": task_id,
            "agent_key": agent_key,
            "tokens_used": tokens_used,
            "timestamp": now,
        })
        
        # Check budget
        directive = await db.directives.find_one({"directive_id": directive_id}, {"_id": 0, "cost_controls": 1})
        budget = (directive.get("cost_controls") or {}).get("global_token_budget", 5000000) if directive else 5000000
        alert_pct = (directive.get("cost_controls") or {}).get("alert_at_percentage", 80) if directive else 80
        
        pipeline = [
            {"$match": {"directive_id": directive_id}},
            {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
        ]
        result = [r async for r in db.directive_cost_tracking.aggregate(pipeline)]
        total_used = result[0]["total"] if result else 0
        pct = round(total_used / budget * 100) if budget > 0 else 0
        
        alert = pct >= alert_pct
        if alert:
            await db.directive_audit_events.insert_one({
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "event_type": "budget_alert",
                "directive_id": directive_id,
                "payload": {"total_used": total_used, "budget": budget, "percentage": pct},
                "timestamp": now,
            })
        
        return {"total_tokens": total_used, "budget": budget, "percentage": pct, "alert": alert}

    @api_router.get("/directives/{directive_id}/cost")
    async def get_cost_summary(directive_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        pipeline = [
            {"$match": {"directive_id": directive_id}},
            {"$group": {"_id": "$agent_key", "tokens": {"$sum": "$tokens_used"}, "calls": {"$sum": 1}}},
        ]
        by_agent = [r async for r in db.directive_cost_tracking.aggregate(pipeline)]
        total_pipeline = [
            {"$match": {"directive_id": directive_id}},
            {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
        ]
        total_result = [r async for r in db.directive_cost_tracking.aggregate(total_pipeline)]
        total = total_result[0]["total"] if total_result else 0
        directive = await db.directives.find_one({"directive_id": directive_id}, {"_id": 0, "cost_controls": 1})
        budget = (directive.get("cost_controls") or {}).get("global_token_budget", 5000000) if directive else 5000000
        return {
            "total_tokens": total,
            "budget": budget,
            "percentage": round(total / budget * 100) if budget > 0 else 0,
            "by_agent": [{"agent": r["_id"], "tokens": r["tokens"], "calls": r["calls"]} for r in by_agent],
        }

    # ===== Conflict Detection =====

    @api_router.post("/directives/{directive_id}/check-conflicts")
    async def check_file_conflicts(directive_id: str, request: Request):
        """Detect if multiple agents are editing the same file"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        
        # Find in-progress tasks with target files
        active_tasks = await db.directive_tasks.find(
            {"directive_id": directive_id, "status": {"$in": ["in_progress", "validation"]}, "target_file": {"$ne": ""}},
            {"_id": 0, "task_id": 1, "assigned_agent": 1, "target_file": 1, "title": 1}
        ).to_list(100)
        
        # Group by file
        file_agents = {}
        for t in active_tasks:
            fp = t.get("target_file", "")
            if fp:
                if fp not in file_agents:
                    file_agents[fp] = []
                file_agents[fp].append(t)
        
        conflicts = []
        for fp, tasks in file_agents.items():
            if len(tasks) > 1:
                conflicts.append({
                    "file": fp,
                    "agents": [{"agent": t["assigned_agent"], "task": t["title"], "task_id": t["task_id"]} for t in tasks],
                })
        
        return {"conflicts": conflicts, "has_conflicts": len(conflicts) > 0}

    # ===== Dashboard Metrics =====

    @api_router.get("/directives/{directive_id}/dashboard")
    async def get_directive_dashboard(directive_id: str, request: Request):
        """Full dashboard with phase progress, agent stats, cost, conflicts"""
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_directive_access
        await require_directive_access(db, user, directive_id)
        
        directive = await db.directives.find_one({"directive_id": directive_id}, {"_id": 0})
        if not directive:
            raise HTTPException(404, "Directive not found")
        
        # Phase progress
        phases = []
        for i, phase in enumerate(directive.get("phases") or []):
            pid = f"phase_{i}"
            total = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": pid})
            merged = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": pid, "status": "merged"})
            in_prog = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": pid, "status": "in_progress"})
            failed = await db.directive_tasks.count_documents({"directive_id": directive_id, "phase_id": pid, "status": {"$in": ["failed", "escalated"]}})
            phases.append({
                "phase_id": pid, "name": phase.get("name", f"Phase {i}"),
                "total": total, "merged": merged, "in_progress": in_prog, "failed": failed,
                "progress": round(merged / total * 100) if total > 0 else 0,
                "gate_passed": total > 0 and merged == total,
            })
        
        # Agent stats
        agent_pipeline = [
            {"$match": {"directive_id": directive_id}},
            {"$group": {"_id": "$assigned_agent", "total": {"$sum": 1},
                        "merged": {"$sum": {"$cond": [{"$eq": ["$status", "merged"]}, 1, 0]}},
                        "failed": {"$sum": {"$cond": [{"$in": ["$status", ["failed", "escalated"]]}, 1, 0]}}}},
        ]
        agent_stats = [r async for r in db.directive_tasks.aggregate(agent_pipeline)]
        
        # Cost
        cost_pipeline = [
            {"$match": {"directive_id": directive_id}},
            {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
        ]
        cost_result = [r async for r in db.directive_cost_tracking.aggregate(cost_pipeline)]
        total_cost = cost_result[0]["total"] if cost_result else 0
        budget = (directive.get("cost_controls") or {}).get("global_token_budget", 5000000)
        
        # Overall
        total_tasks = await db.directive_tasks.count_documents({"directive_id": directive_id})
        done_tasks = await db.directive_tasks.count_documents({"directive_id": directive_id, "status": "merged"})
        escalated = await db.directive_tasks.count_documents({"directive_id": directive_id, "status": "escalated"})
        
        return {
            "directive": {"project_name": directive["project_name"], "goal": directive.get("goal", ""), "is_active": directive.get("is_active", False)},
            "overall": {"total": total_tasks, "done": done_tasks, "escalated": escalated, "progress": round(done_tasks / total_tasks * 100) if total_tasks > 0 else 0},
            "phases": phases,
            "agent_stats": [{"agent": r["_id"], "total": r["total"], "merged": r["merged"], "failed": r["failed"]} for r in agent_stats],
            "cost": {"total_tokens": total_cost, "budget": budget, "percentage": round(total_cost / budget * 100) if budget > 0 else 0},
        }
