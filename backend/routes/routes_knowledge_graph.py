"""Knowledge Graph API — Browse, search, correct, and manage institutional knowledge."""
from nexus_utils import now_iso, gen_id, require_workspace_access
from fastapi import HTTPException, Request


def register_knowledge_graph_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/knowledge")
    async def list_knowledge_entities(ws_id: str, request: Request,
                                      entity_type: str = None, search: str = None, limit: int = 50):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        query = {"workspace_id": ws_id, "is_active": True}
        if entity_type:
            query["entity_type"] = entity_type
        if search:
            from nexus_utils import safe_regex
            query["$or"] = [
                {"name": {"$regex": safe_regex(search), "$options": "i"}},
                {"description": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        entities = await db.kg_entities.find(query, {"_id": 0}
        ).sort("access_count", -1).limit(min(limit, 200)).to_list(min(limit, 200))
        return {"entities": entities, "total": len(entities)}

    @api_router.get("/workspaces/{ws_id}/knowledge/graph")
    async def get_knowledge_graph_visualization(ws_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        entities = await db.kg_entities.find(
            {"workspace_id": ws_id, "is_active": True},
            {"_id": 0, "entity_id": 1, "name": 1, "entity_type": 1, "confidence": 1, "access_count": 1}
        ).sort("access_count", -1).limit(100).to_list(100)
        edges = await db.kg_edges.find(
            {"workspace_id": ws_id},
            {"_id": 0, "source_entity_id": 1, "target_entity_id": 1, "relationship": 1, "strength": 1}
        ).limit(500).to_list(500)
        return {"nodes": entities, "edges": edges}

    @api_router.get("/workspaces/{ws_id}/knowledge/{entity_id}")
    async def get_knowledge_entity(ws_id: str, entity_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        entity = await db.kg_entities.find_one(
            {"entity_id": entity_id, "workspace_id": ws_id}, {"_id": 0})
        if not entity:
            raise HTTPException(404, "Entity not found")
        edges = await db.kg_edges.find(
            {"workspace_id": ws_id, "$or": [
                {"source_entity_id": entity_id}, {"target_entity_id": entity_id}
            ]}, {"_id": 0}).limit(50).to_list(50)
        return {"entity": entity, "relationships": edges}

    @api_router.post("/workspaces/{ws_id}/knowledge/{entity_id}/feedback")
    async def submit_knowledge_feedback(ws_id: str, entity_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        action = body.get("action", "upvote")
        feedback = {
            "feedback_id": gen_id("kgf"), "entity_id": entity_id,
            "user_id": user["user_id"], "action": action,
            "correction": body.get("correction", ""), "created_at": now_iso(),
        }
        await db.kg_feedback.insert_one(feedback)
        if action == "upvote":
            await db.kg_entities.update_one({"entity_id": entity_id},
                {"$inc": {"confidence": 0.05}, "$set": {"updated_at": now_iso()}})
        elif action == "downvote":
            await db.kg_entities.update_one({"entity_id": entity_id},
                {"$inc": {"confidence": -0.1}, "$set": {"updated_at": now_iso()}})
        elif action == "correct":
            await db.kg_entities.update_one({"entity_id": entity_id},
                {"$set": {"description": body.get("correction", ""), "updated_at": now_iso()}})
        elif action == "delete":
            await db.kg_entities.update_one({"entity_id": entity_id},
                {"$set": {"is_active": False, "updated_at": now_iso()}})
        return {"status": "feedback_recorded", "action": action}

    @api_router.post("/workspaces/{ws_id}/knowledge/edges")
    async def create_explicit_edge(ws_id: str, request: Request):
        """Create a typed relationship between two entities."""
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        source_id = body.get("source_entity_id", "")
        target_id = body.get("target_entity_id", "")
        relationship = body.get("relationship", "related_to")
        evidence = body.get("evidence", "")
        if not source_id or not target_id:
            raise HTTPException(400, "source_entity_id and target_entity_id required")
        from knowledge_graph import KnowledgeGraphEngine
        kg = KnowledgeGraphEngine(db)
        edge_id = await kg.add_explicit_edge(ws_id, source_id, target_id, relationship, evidence)
        return {"edge_id": edge_id, "status": "created"}

    @api_router.post("/workspaces/{ws_id}/knowledge/{entity_id}/supersede")
    async def supersede_entity(ws_id: str, entity_id: str, request: Request):
        """Mark entity as superseded by a newer one."""
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        new_entity_id = body.get("new_entity_id", "")
        if not new_entity_id:
            raise HTTPException(400, "new_entity_id required")
        from knowledge_graph import KnowledgeGraphEngine
        kg = KnowledgeGraphEngine(db)
        await kg.supersede_entity(ws_id, entity_id, new_entity_id)
        return {"status": "superseded", "old": entity_id, "new": new_entity_id}

    @api_router.get("/workspaces/{ws_id}/knowledge/{entity_id}/neighborhood")
    async def get_entity_neighborhood(ws_id: str, entity_id: str, request: Request, depth: int = 1):
        """Get entity + all connected entities up to N hops for graph exploration."""
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        from knowledge_graph import KnowledgeGraphEngine
        kg = KnowledgeGraphEngine(db)
        return await kg.get_entity_neighborhood(ws_id, entity_id, min(depth, 3))

    @api_router.put("/workspaces/{ws_id}/knowledge-graph/settings")
    async def update_workspace_kg_settings(ws_id: str, request: Request):
        """Toggle workspace KG. Owner only."""
        user = await get_current_user(request)
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "owner_id": 1})
        if not ws:
            raise HTTPException(404, "Workspace not found")
        if ws.get("owner_id") != user["user_id"]:
            raise HTTPException(403, "Only workspace owner can manage Knowledge Graph settings")
        body = await request.json()
        updates = {"updated_at": now_iso()}
        if "enabled" in body:
            enabled = bool(body["enabled"])
            updates["knowledge_graph.enabled"] = enabled
            updates["knowledge_graph.consented_by"] = user["user_id"] if enabled else None
            updates["knowledge_graph.consented_at"] = now_iso() if enabled else None
            if not enabled:
                from knowledge_graph import _schedule_kg_purge
                await _schedule_kg_purge(db, ws_id, "workspace")
        if "share_with_org" in body:
            updates["knowledge_graph.share_with_org"] = bool(body["share_with_org"])
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": updates})
        await db.kg_consent_audit.insert_one({
            "audit_id": gen_id("kga"), "workspace_id": ws_id,
            "org_id": (await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "org_id": 1}) or {}).get("org_id", ""),
            "changed_by": user["user_id"], "changes": body,
            "timestamp": now_iso(), "consent_version": "1.0",
        })
        return {"status": "updated"}

    @api_router.get("/workspaces/{ws_id}/knowledge-graph/consent-summary")
    async def get_workspace_consent_summary(ws_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "org_id": 1})
        org_id = (ws or {}).get("org_id", "")
        from knowledge_graph import ConsentChecker
        return await ConsentChecker.get_consent_summary(db, ws_id, org_id)
