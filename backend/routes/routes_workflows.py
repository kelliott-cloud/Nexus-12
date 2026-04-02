"""Workflow API routes - CRUD, runs, templates, SSE streaming"""
import uuid
import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from nexus_utils import now_iso
from workflow_engine import WorkflowOrchestrator, SSEManager

sse_manager = SSEManager()


# ============ Models ============

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    template_id: Optional[str] = None

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class WorkflowRunCreate(BaseModel):
    input: dict = {}

class GateApproval(BaseModel):
    action: str  # "approved" or "rejected"
    feedback: Optional[str] = None
    edited_output: Optional[dict] = None

class NodeCreate(BaseModel):
    type: str
    label: str = "New Node"
    ai_model: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    input_schema: dict = {}
    output_schema: dict = {}
    condition_logic: Optional[dict] = None
    timeout_seconds: int = 120
    retry_count: int = 1
    position_x: float = 0
    position_y: float = 0
    merge_strategy: Optional[str] = None
    checkpoint_type: Optional[str] = None
    timeout_minutes: Optional[int] = None
    trigger_config: Optional[dict] = None  # {type: webhook|cron|event, webhook_url, cron_expr, event_name}

class NodeUpdate(BaseModel):
    label: Optional[str] = None
    ai_model: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    condition_logic: Optional[dict] = None
    timeout_seconds: Optional[int] = None
    retry_count: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    merge_strategy: Optional[str] = None
    checkpoint_type: Optional[str] = None
    timeout_minutes: Optional[int] = None
    trigger_config: Optional[dict] = None

class EdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: str = "default"
    label: Optional[str] = None

class CanvasSave(BaseModel):
    nodes: List[dict] = []
    edges: List[dict] = []


VALID_WF_STATUSES = ["draft", "active", "paused", "archived"]
VALID_NODE_TYPES = ["ai_agent", "human_review", "condition", "merge", "input", "output", "trigger",
                     "text_to_video", "image_to_video", "text_to_speech", "text_to_music",
                     "sound_effect", "transcribe", "video_compose", "audio_compose", "media_publish"]

# Workflow RBAC permissions
WF_PERMISSIONS = {
    "owner": {"view": True, "edit": True, "activate": True, "run": True, "delete": True},
    "admin": {"view": True, "edit": True, "activate": True, "run": True, "delete": True},
    "moderator": {"view": True, "edit": True, "activate": False, "run": True, "delete": False},
    "user": {"view": True, "edit": False, "activate": False, "run": False, "delete": False},
    "viewer": {"view": True, "edit": False, "activate": False, "run": False, "delete": False},
}


from nexus_utils import safe_regex

def register_workflow_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    orchestrator = WorkflowOrchestrator(db, sse_manager)

    # ============ Templates ============

    @api_router.get("/templates")
    async def list_templates(request: Request, category: Optional[str] = None, difficulty: Optional[str] = None, search: Optional[str] = None):
        await get_current_user(request)
        query = {"is_active": True}
        if category:
            query["category"] = category
        if difficulty:
            query["difficulty"] = difficulty
        if search:
            query["$or"] = [
                {"name": {"$regex": safe_regex(search), "$options": "i"}},
                {"description": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        templates = await db.workflow_templates.find(query, {"_id": 0}).sort("is_featured", -1).to_list(50)
        return templates

    @api_router.get("/templates/{template_id}")
    async def get_template(template_id: str, request: Request):
        await get_current_user(request)
        t = await db.workflow_templates.find_one({"template_id": template_id}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Template not found")
        return t

    # ============ Workflow CRUD ============

    @api_router.post("/workspaces/{workspace_id}/workflows")
    async def create_workflow(workspace_id: str, data: WorkflowCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        now = now_iso()
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"

        workflow = {
            "workflow_id": workflow_id,
            "workspace_id": workspace_id,
            "name": data.name.strip(),
            "description": data.description.strip(),
            "status": "draft",
            "template_id": data.template_id,
            "created_by": user["user_id"],
            "is_template_instance": bool(data.template_id),
            "run_count": 0,
            "last_run_at": None,
            "created_at": now,
            "updated_at": now,
        }
        await db.workflows.insert_one(workflow)

        nodes_created = []
        edges_created = []

        if data.template_id:
            template = await db.workflow_templates.find_one({"template_id": data.template_id}, {"_id": 0})
            if not template:
                raise HTTPException(404, "Template not found")

            # Support both template formats: nodes/edges or node_definitions/edge_definitions
            tpl_nodes = template.get("nodes", template.get("node_definitions") or [])
            tpl_edges = template.get("edges", template.get("edge_definitions") or [])

            node_id_map = {}  # template id/label -> new node_id
            for idx, nd in enumerate(tpl_nodes):
                node_id = f"wn_{uuid.uuid4().hex[:12]}"
                tpl_id = nd.get("id", nd.get("label", str(idx)))
                node_id_map[tpl_id] = node_id
                # Also map by label for edge resolution
                if nd.get("label"):
                    node_id_map[nd["label"]] = node_id
                node = {
                    "node_id": node_id, "workflow_id": workflow_id, "type": nd["type"],
                    "label": nd.get("label", f"Step {idx}"), "position": idx,
                    "ai_model": nd.get("ai_model"), "system_prompt": nd.get("system_prompt"),
                    "user_prompt_template": nd.get("user_prompt_template"),
                    "temperature": nd.get("temperature", 0.7), "max_tokens": nd.get("max_tokens", 4096),
                    "input_schema": nd.get("input_schema") or {}, "output_schema": nd.get("output_schema") or {},
                    "condition_logic": nd.get("condition_logic"), "timeout_seconds": nd.get("timeout_seconds", 120),
                    "retry_count": nd.get("retry_count", 1),
                    "position_x": nd.get("position_x", 250), "position_y": nd.get("position_y", idx * 150),
                    "created_at": now,
                }
                await db.workflow_nodes.insert_one(node)
                nodes_created.append({k: v for k, v in node.items() if k != "_id"})

            # Create edges from template
            for ed in tpl_edges:
                src_key = ed.get("source", ed.get("source_label", ed.get("source_node_id", "")))
                tgt_key = ed.get("target", ed.get("target_label", ed.get("target_node_id", "")))
                src_id = node_id_map.get(src_key)
                tgt_id = node_id_map.get(tgt_key)
                if src_id and tgt_id:
                    edge_id = f"we_{uuid.uuid4().hex[:12]}"
                    edge = {
                        "edge_id": edge_id, "workflow_id": workflow_id,
                        "source_node_id": src_id, "target_node_id": tgt_id,
                        "edge_type": ed.get("edge_type", "default"),
                        "label": ed.get("label"),
                        "created_at": now,
                    }
                    await db.workflow_edges.insert_one(edge)
                    edges_created.append({k: v for k, v in edge.items() if k != "_id"})

            # Update condition nodes with actual node IDs
            for nd in nodes_created:
                if nd["type"] == "condition" and nd.get("condition_logic"):
                    cl = nd["condition_logic"]
                    updated = False
                    for key in ["true_target", "false_target"]:
                        if cl.get(key) and cl[key] in node_id_map:
                            cl[key] = node_id_map[cl[key]]
                            updated = True
                    if updated:
                        await db.workflow_nodes.update_one({"node_id": nd["node_id"]}, {"$set": {"condition_logic": cl}})

            await db.workflow_templates.update_one({"template_id": data.template_id}, {"$inc": {"usage_count": 1}})
            workflow["status"] = "active"
            await db.workflows.update_one({"workflow_id": workflow_id}, {"$set": {"status": "active"}})

        result = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not result:
            raise HTTPException(500, "Created but could not retrieve")
        result["nodes"] = nodes_created
        result["edges"] = edges_created
        return result

    @api_router.get("/workspaces/{workspace_id}/workflows")
    async def list_workflows(workspace_id: str, request: Request, status: Optional[str] = None):
        user = await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if status:
            query["status"] = status
        workflows = await db.workflows.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
        # Enrich with node counts
        for wf in workflows:
            wf["node_count"] = await db.workflow_nodes.count_documents({"workflow_id": wf["workflow_id"]})
        return workflows

    @api_router.get("/workflows/{workflow_id}")
    async def get_workflow(workflow_id: str, request: Request):
        await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")
        wf["nodes"] = await db.workflow_nodes.find({"workflow_id": workflow_id}, {"_id": 0}).sort("position", 1).to_list(100)
        wf["edges"] = await db.workflow_edges.find({"workflow_id": workflow_id}, {"_id": 0}).to_list(200)
        return wf

    @api_router.put("/workflows/{workflow_id}")
    async def update_workflow(workflow_id: str, data: WorkflowUpdate, request: Request):
        await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id})
        if not wf:
            raise HTTPException(404, "Workflow not found")
        updates = {"updated_at": now_iso()}
        if data.name is not None:
            updates["name"] = data.name.strip()
        if data.description is not None:
            updates["description"] = data.description.strip()
        if data.status is not None:
            if data.status not in VALID_WF_STATUSES:
                raise HTTPException(400, f"Invalid status. Use: {', '.join(VALID_WF_STATUSES)}")
            updates["status"] = data.status
        await db.workflows.update_one({"workflow_id": workflow_id}, {"$set": updates})
        return await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})

    @api_router.delete("/workflows/{workflow_id}")
    async def delete_workflow(workflow_id: str, request: Request):
        user = await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"workspace_id": 1})
        if not wf: raise HTTPException(404, "Workflow not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, wf["workspace_id"])
        running = await db.workflow_runs.count_documents({"workflow_id": workflow_id, "status": "running"})
        if running:
            raise HTTPException(409, "Cannot delete workflow with active runs")
        await db.workflow_nodes.delete_many({"workflow_id": workflow_id})
        await db.workflow_edges.delete_many({"workflow_id": workflow_id})
        await db.node_executions.delete_many({"run_id": {"$in": [r["run_id"] async for r in db.workflow_runs.find({"workflow_id": workflow_id}, {"run_id": 1})]}})
        await db.workflow_runs.delete_many({"workflow_id": workflow_id})
        await db.workflows.delete_one({"workflow_id": workflow_id})
        return {"message": "Workflow deleted"}

    # ============ Node CRUD ============

    @api_router.post("/workflows/{workflow_id}/nodes")
    async def create_node(workflow_id: str, data: NodeCreate, request: Request):
        await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id})
        if not wf:
            raise HTTPException(404, "Workflow not found")
        if data.type not in VALID_NODE_TYPES:
            raise HTTPException(400, f"Invalid node type. Use: {', '.join(VALID_NODE_TYPES)}")
        node_count = await db.workflow_nodes.count_documents({"workflow_id": workflow_id})
        node_id = f"wn_{uuid.uuid4().hex[:12]}"
        node = {
            "node_id": node_id, "workflow_id": workflow_id, "type": data.type,
            "label": data.label, "position": node_count,
            "ai_model": data.ai_model, "system_prompt": data.system_prompt,
            "user_prompt_template": data.user_prompt_template,
            "temperature": data.temperature, "max_tokens": data.max_tokens,
            "input_schema": data.input_schema, "output_schema": data.output_schema,
            "condition_logic": data.condition_logic, "timeout_seconds": data.timeout_seconds,
            "retry_count": data.retry_count,
            "position_x": data.position_x, "position_y": data.position_y,
            "created_at": now_iso(),
        }
        await db.workflow_nodes.insert_one(node)
        return {k: v for k, v in node.items() if k != "_id"}

    @api_router.put("/workflows/{workflow_id}/nodes/{node_id}")
    async def update_node(workflow_id: str, node_id: str, data: NodeUpdate, request: Request):
        await get_current_user(request)
        node = await db.workflow_nodes.find_one({"node_id": node_id, "workflow_id": workflow_id})
        if not node:
            raise HTTPException(404, "Node not found")
        updates = {}
        for field, val in data.dict(exclude_unset=True).items():
            if val is not None:
                updates[field] = val
        if updates:
            await db.workflow_nodes.update_one({"node_id": node_id}, {"$set": updates})
        return await db.workflow_nodes.find_one({"node_id": node_id}, {"_id": 0})

    @api_router.delete("/workflows/{workflow_id}/nodes/{node_id}")
    async def delete_node(workflow_id: str, node_id: str, request: Request):
        await get_current_user(request)
        node = await db.workflow_nodes.find_one({"node_id": node_id, "workflow_id": workflow_id})
        if not node:
            raise HTTPException(404, "Node not found")
        await db.workflow_edges.delete_many({"workflow_id": workflow_id, "$or": [{"source_node_id": node_id}, {"target_node_id": node_id}]})
        await db.workflow_nodes.delete_one({"node_id": node_id})
        return {"message": "Node deleted"}

    # ============ Edge CRUD ============

    @api_router.post("/workflows/{workflow_id}/edges")
    async def create_edge(workflow_id: str, data: EdgeCreate, request: Request):
        await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id})
        if not wf:
            raise HTTPException(404, "Workflow not found")
        edge_id = f"we_{uuid.uuid4().hex[:12]}"
        edge = {
            "edge_id": edge_id, "workflow_id": workflow_id,
            "source_node_id": data.source_node_id, "target_node_id": data.target_node_id,
            "edge_type": data.edge_type, "label": data.label, "created_at": now_iso(),
        }
        await db.workflow_edges.insert_one(edge)
        return {k: v for k, v in edge.items() if k != "_id"}

    @api_router.delete("/workflows/{workflow_id}/edges/{edge_id}")
    async def delete_edge(workflow_id: str, edge_id: str, request: Request):
        await get_current_user(request)
        edge = await db.workflow_edges.find_one({"edge_id": edge_id, "workflow_id": workflow_id})
        if not edge:
            raise HTTPException(404, "Edge not found")
        await db.workflow_edges.delete_one({"edge_id": edge_id})
        return {"message": "Edge deleted"}

    # ============ Canvas Save (batch update) ============

    @api_router.put("/workflows/{workflow_id}/canvas")
    async def save_canvas(workflow_id: str, data: CanvasSave, request: Request):
        """Batch save all node positions and edges from the canvas"""
        await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        # Update node positions
        for nd in data.nodes:
            node_id = nd.get("node_id") or nd.get("id")
            if not node_id:
                continue
            updates = {}
            if "position_x" in nd:
                updates["position_x"] = nd["position_x"]
            if "position_y" in nd:
                updates["position_y"] = nd["position_y"]
            if "label" in nd:
                updates["label"] = nd["label"]
            if updates:
                await db.workflow_nodes.update_one({"node_id": node_id, "workflow_id": workflow_id}, {"$set": updates})

        # Sync edges: delete removed, add new
        existing_edges = await db.workflow_edges.find({"workflow_id": workflow_id}, {"_id": 0}).to_list(200)
        existing_edge_ids = {e["edge_id"] for e in existing_edges}
        new_edge_ids = {e.get("edge_id") or e.get("id", "") for e in data.edges}

        # Delete edges not in new set
        to_delete = existing_edge_ids - new_edge_ids
        if to_delete:
            await db.workflow_edges.delete_many({"edge_id": {"$in": list(to_delete)}, "workflow_id": workflow_id})

        # Add new edges
        for ed in data.edges:
            eid = ed.get("edge_id") or ed.get("id", "")
            if eid not in existing_edge_ids:
                edge_id = eid or f"we_{uuid.uuid4().hex[:12]}"
                await db.workflow_edges.insert_one({
                    "edge_id": edge_id, "workflow_id": workflow_id,
                    "source_node_id": ed.get("source_node_id", ed.get("source", "")),
                    "target_node_id": ed.get("target_node_id", ed.get("target", "")),
                    "edge_type": ed.get("edge_type", "default"), "label": ed.get("label"),
                    "created_at": now_iso(),
                })

        await db.workflows.update_one({"workflow_id": workflow_id}, {"$set": {"updated_at": now_iso()}})
        return {"message": "Canvas saved"}

    # ============ Runs ============

    @api_router.post("/workflows/{workflow_id}/run")
    async def run_workflow(workflow_id: str, data: WorkflowRunCreate, request: Request):
        user = await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")
        if wf["status"] != "active":
            raise HTTPException(400, "Workflow must be activated before running.")

        # Validate API keys for all AI agent nodes
        nodes = await db.workflow_nodes.find({"workflow_id": workflow_id, "type": "ai_agent"}, {"_id": 0}).to_list(50)
        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_keys": 1})
        ai_keys = user_doc.get("ai_keys") or {} if user_doc else {}
        missing_models = []
        for n in nodes:
            model = n.get("ai_model")
            if model and not ai_keys.get(model):
                missing_models.append(model)
        if missing_models:
            raise HTTPException(400, f"Missing API keys for: {', '.join(set(missing_models))}. Configure them in Settings.")

        run_id = f"wrun_{uuid.uuid4().hex[:12]}"
        run = {
            "run_id": run_id, "workflow_id": workflow_id, "status": "queued",
            "triggered_by": "manual", "run_by": user["user_id"],
            "initial_input": data.input, "final_output": None,
            "current_node_id": None, "total_tokens": 0, "total_cost_usd": 0,
            "total_duration_ms": 0, "error_message": None, "error_node_id": None,
            "started_at": None, "completed_at": None, "created_at": now_iso(),
        }
        await db.workflow_runs.insert_one(run)

        # Execute in background
        asyncio.create_task(orchestrator.execute_workflow(run_id))

        return {"run_id": run_id, "status": "queued", "message": "Workflow execution started.", "websocket_channel": f"workflow-run:{run_id}"}

    @api_router.get("/workflows/{workflow_id}/runs")
    async def list_runs(workflow_id: str, request: Request):
        await get_current_user(request)
        runs = await db.workflow_runs.find({"workflow_id": workflow_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return runs

    @api_router.get("/workflow-runs/{run_id}")
    async def get_run(run_id: str, request: Request):
        await get_current_user(request)
        run = await db.workflow_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        run["node_executions"] = await db.node_executions.find({"run_id": run_id}, {"_id": 0}).sort("started_at", 1).to_list(200)
        # Enrich with node labels
        node_ids = list({ex["node_id"] for ex in run["node_executions"]})
        nodes = await db.workflow_nodes.find({"node_id": {"$in": node_ids}}, {"_id": 0}).to_list(100)
        node_map = {n["node_id"]: n for n in nodes}
        for ex in run["node_executions"]:
            n = node_map.get(ex["node_id"], {})
            ex["node_label"] = n.get("label", "Unknown")
            ex["node_type"] = n.get("type", "unknown")
            ex["node_model"] = n.get("ai_model")
            ex["node_position"] = n.get("position", 0)
        return run

    @api_router.get("/workflow-runs/{run_id}/logs")
    async def get_run_execution_logs(run_id: str, request: Request):
        """Get detailed execution logs for a workflow run - timeline of all node executions"""
        await get_current_user(request)
        run = await db.workflow_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        executions = await db.node_executions.find(
            {"run_id": run_id}, {"_id": 0}
        ).sort("started_at", 1).to_list(200)
        # Enrich with node metadata
        node_ids = list({ex["node_id"] for ex in executions})
        nodes = await db.workflow_nodes.find({"node_id": {"$in": node_ids}}, {"_id": 0}).to_list(100)
        node_map = {n["node_id"]: n for n in nodes}
        logs = []
        for ex in executions:
            n = node_map.get(ex["node_id"], {})
            logs.append({
                "exec_id": ex["exec_id"],
                "node_id": ex["node_id"],
                "node_label": n.get("label", "Unknown"),
                "node_type": n.get("type", "unknown"),
                "ai_model": n.get("ai_model"),
                "status": ex["status"],
                "attempt": ex.get("attempt", 1),
                "started_at": ex.get("started_at"),
                "completed_at": ex.get("completed_at"),
                "duration_ms": ex.get("duration_ms", 0),
                "tokens_total": ex.get("tokens_total", 0),
                "cost_usd": ex.get("cost_usd", 0),
                "error_message": ex.get("error_message"),
                "error_type": ex.get("error_type"),
                "output_summary": json.dumps(ex.get("output_data") or {})[:200] if ex.get("output_data") else None,
            })
        return {
            "run_id": run_id,
            "status": run["status"],
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "total_tokens": run.get("total_tokens", 0),
            "total_cost_usd": run.get("total_cost_usd", 0),
            "total_duration_ms": run.get("total_duration_ms", 0),
            "logs": logs,
        }


    @api_router.post("/workflow-runs/{run_id}/cancel")
    async def cancel_run(run_id: str, request: Request):
        await get_current_user(request)
        run = await db.workflow_runs.find_one({"run_id": run_id})
        if not run:
            raise HTTPException(404, "Run not found")
        if run["status"] not in ("running", "queued", "paused_at_gate"):
            raise HTTPException(400, "Run is not active")
        await db.node_executions.update_many({"run_id": run_id, "status": {"$in": ["pending", "running", "waiting_human"]}}, {"$set": {"status": "skipped", "completed_at": now_iso()}})
        totals_result = await orchestrator._calc_run_totals(run_id)
        await db.workflow_runs.update_one({"run_id": run_id}, {"$set": {"status": "cancelled", "completed_at": now_iso(), **totals_result}})
        await sse_manager.send(run_id, {"event": "run:cancelled", "run_id": run_id, "status": "cancelled"})
        return {"message": "Run cancelled"}

    @api_router.post("/workflow-runs/{run_id}/nodes/{node_id}/approve")
    async def approve_gate(run_id: str, node_id: str, data: GateApproval, request: Request):
        await get_current_user(request)
        if data.action not in ("approved", "rejected"):
            raise HTTPException(400, "Action must be 'approved' or 'rejected'")
        success = await orchestrator.resume_after_gate(run_id, node_id, data.action, data.edited_output, data.feedback)
        if not success:
            raise HTTPException(400, "Run is not paused at this gate")
        return {"message": f"Gate {data.action}", "status": "resumed" if data.action == "approved" else "failed"}

    # ============ SSE Stream ============

    @api_router.get("/workflow-runs/{run_id}/stream")
    async def stream_run(run_id: str, request: Request):
        await get_current_user(request)
        q = sse_manager.subscribe(run_id)

        async def event_generator():
            try:
                while True:
                    try:
                        data = await asyncio.wait_for(q.get(), timeout=30)
                        yield f"data: {json.dumps(data)}\n\n"
                        if data.get("event") in ("run:completed", "run:failed", "run:cancelled"):
                            break
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'event': 'heartbeat'})}\n\n"
            finally:
                sse_manager.unsubscribe(run_id, q)

        return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


    # ============ RBAC — Workflow Permissions (#18) ============

    @api_router.get("/workflows/{workflow_id}/permissions")
    async def get_workflow_permissions(workflow_id: str, request: Request):
        """Get current user's permissions for this workflow"""
        user = await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0, "workspace_id": 1, "created_by": 1})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        # Determine role
        ws = await db.workspaces.find_one({"workspace_id": wf.get("workspace_id", "")}, {"_id": 0, "owner_id": 1, "members": 1})
        role = "viewer"
        if ws:
            if ws.get("owner_id") == user["user_id"]:
                role = "owner"
            elif user.get("platform_role") in ("super_admin", "admin"):
                role = "admin"
            elif user["user_id"] in ws.get("members") or []:
                role = "user"
                if wf.get("created_by") == user["user_id"]:
                    role = "moderator"  # Creator gets elevated permissions on own workflows

        perms = WF_PERMISSIONS.get(role, WF_PERMISSIONS["viewer"])
        return {"role": role, "permissions": perms}

    # ============ Variable Schema (#6) ============

    @api_router.get("/workflows/{workflow_id}/variables")
    async def get_workflow_variables(workflow_id: str, request: Request):
        """Get available variables for data mapping between nodes"""
        await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        nodes_list = await db.workflow_nodes.find({"workflow_id": workflow_id}, {"_id": 0}).to_list(50)
        variables = []

        for node in nodes_list:
            node_label = node.get("label", node["node_id"]).lower().replace(" ", "_")
            node_type = node.get("type", "")

            if node_type == "input":
                variables.append({"source": node_label, "field": "text", "type": "string", "description": "Input text data"})
                variables.append({"source": node_label, "field": "data", "type": "object", "description": "Full input object"})
                # Add schema fields if defined
                for key, cfg in node.get("input_schema") or {}.items():
                    variables.append({"source": node_label, "field": key, "type": cfg.get("type", "string"), "description": cfg.get("label", key)})

            elif node_type == "ai_agent":
                variables.append({"source": node_label, "field": "response", "type": "string", "description": f"AI response from {node.get('label', 'Agent')}"})
                variables.append({"source": node_label, "field": "tokens", "type": "number", "description": "Token count"})
                variables.append({"source": node_label, "field": "model", "type": "string", "description": "Model used"})

            elif node_type == "condition":
                variables.append({"source": node_label, "field": "result", "type": "boolean", "description": "Condition evaluation result"})

            elif node_type == "merge":
                variables.append({"source": node_label, "field": "merged", "type": "object", "description": "Merged data from all branches"})

            elif node_type == "human_review":
                variables.append({"source": node_label, "field": "action", "type": "string", "description": "Reviewer action (approved/rejected)"})
                variables.append({"source": node_label, "field": "feedback", "type": "string", "description": "Reviewer feedback"})

            elif node_type == "trigger":
                variables.append({"source": node_label, "field": "payload", "type": "object", "description": "Trigger payload data"})
                variables.append({"source": node_label, "field": "trigger_type", "type": "string", "description": "How the workflow was triggered"})

        return {"variables": variables, "syntax": "{{source.field}}", "example": "{{input.text}}"}

    # ============ Trigger Node Config (#14) ============

    @api_router.post("/workflows/{workflow_id}/trigger/webhook")
    async def create_workflow_webhook_trigger(workflow_id: str, request: Request):
        """Generate a webhook URL that triggers this workflow"""
        user = await get_current_user(request)
        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        import secrets
        token = secrets.token_urlsafe(24)
        hook_id = f"wft_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        await db.workflow_triggers.insert_one({
            "trigger_id": hook_id, "workflow_id": workflow_id,
            "workspace_id": wf.get("workspace_id", ""),
            "type": "webhook", "url_token": token,
            "enabled": True, "trigger_count": 0,
            "created_by": user["user_id"], "created_at": now,
        })

        return {
            "trigger_id": hook_id,
            "type": "webhook",
            "webhook_url": f"/api/workflows/trigger/{token}",
            "token": token,
        }

    @api_router.post("/workflows/{workflow_id}/trigger/cron")
    async def create_workflow_cron_trigger(workflow_id: str, request: Request):
        """Create a scheduled cron trigger for this workflow"""
        user = await get_current_user(request)
        body = await request.json()
        cron_expr = body.get("cron", "0 9 * * *")  # Default: daily at 9am
        input_data = body.get("input") or {}

        wf = await db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")

        hook_id = f"wft_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        await db.workflow_triggers.insert_one({
            "trigger_id": hook_id, "workflow_id": workflow_id,
            "workspace_id": wf.get("workspace_id", ""),
            "type": "cron", "cron_expression": cron_expr,
            "input_data": input_data,
            "enabled": True, "trigger_count": 0,
            "created_by": user["user_id"], "created_at": now,
        })

        return {"trigger_id": hook_id, "type": "cron", "cron_expression": cron_expr}

    @api_router.get("/workflows/{workflow_id}/triggers")
    async def list_workflow_triggers(workflow_id: str, request: Request):
        """List all triggers for a workflow"""
        await get_current_user(request)
        triggers = await db.workflow_triggers.find({"workflow_id": workflow_id}, {"_id": 0}).to_list(20)
        for t in triggers:
            if t.get("type") == "webhook":
                t["webhook_url"] = f"/api/workflows/trigger/{t.get('url_token', '')}"
        return {"triggers": triggers}

    @api_router.delete("/workflow-triggers/{trigger_id}")
    async def delete_workflow_trigger(trigger_id: str, request: Request):
        user = await get_current_user(request)
        trigger = await db.workflow_triggers.find_one({"trigger_id": trigger_id}, {"workspace_id": 1})
        if trigger and trigger.get("workspace_id"):
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, trigger["workspace_id"])
        result = await db.workflow_triggers.delete_one({"trigger_id": trigger_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Trigger not found")
        return {"message": "Trigger deleted"}

    @api_router.post("/workflows/trigger/{token}")
    async def fire_webhook_trigger(token: str, request: Request):
        """Public endpoint — fires a workflow via webhook token"""
        trigger = await db.workflow_triggers.find_one({"url_token": token, "enabled": True, "type": "webhook"}, {"_id": 0})
        if not trigger:
            raise HTTPException(404, "Trigger not found or disabled")

        body = {}
        try:
            body = await request.json()
        except Exception as _e:
            logger.warning(f"Caught exception: {_e}")

        # Create and execute run
        run_id = f"wrun_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        await db.workflow_runs.insert_one({
            "run_id": run_id, "workflow_id": trigger["workflow_id"],
            "status": "queued", "triggered_by": "webhook",
            "run_by": trigger.get("created_by", "webhook"),
            "initial_input": body, "final_output": None,
            "current_node_id": None, "total_tokens": 0, "total_cost_usd": 0,
            "total_duration_ms": 0, "started_at": None, "completed_at": None,
            "created_at": now,
        })

        await db.workflow_triggers.update_one(
            {"trigger_id": trigger["trigger_id"]},
            {"$inc": {"trigger_count": 1}, "$set": {"last_triggered_at": now}}
        )

        orchestrator = WorkflowOrchestrator(db, sse_manager)
        asyncio.create_task(orchestrator.execute_workflow(run_id))

        return {"status": "triggered", "run_id": run_id, "workflow_id": trigger["workflow_id"]}
