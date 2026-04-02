"""Institutional Knowledge Graph Engine — Ambient learning with three-tier consent."""
import hashlib
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from nexus_utils import now_iso, gen_id
from semantic_memory import _tokenize

logger = logging.getLogger(__name__)

ENTITY_TYPES = ["decision", "fact", "concept", "person", "tool", "process", "preference"]

EXTRACTION_PROMPT = """Extract knowledge entities from this text. Return JSON: {"entities": [
  {"name": "...", "type": "decision|fact|concept|tool|process|preference",
   "description": "one sentence", "confidence": 0.0-1.0, "tags": ["..."]}
]}
Only extract substantive knowledge — skip greetings, questions, filler.
Text: {text}"""


class ConsentChecker:
    """Centralized consent verification for all KG operations."""

    @staticmethod
    async def is_workspace_kg_enabled(db, workspace_id: str) -> bool:
        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "knowledge_graph": 1})
        return bool((ws or {}).get("knowledge_graph", {}).get("enabled", False))

    @staticmethod
    async def is_tenant_kg_enabled(db, org_id: str) -> bool:
        if not org_id:
            return False
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "knowledge_graph": 1})
        return bool((org or {}).get("knowledge_graph", {}).get("tenant_kg_enabled", False))

    @staticmethod
    async def is_platform_kg_enabled(db, org_id: str) -> bool:
        if not org_id:
            return False
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "knowledge_graph": 1})
        return bool((org or {}).get("knowledge_graph", {}).get("platform_kg_enabled", False))

    @staticmethod
    async def can_workspace_share_to_org(db, workspace_id: str, org_id: str) -> bool:
        if not org_id:
            return False
        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "knowledge_graph": 1})
        ws_kg = (ws or {}).get("knowledge_graph", {})
        if not ws_kg.get("enabled", False) or not ws_kg.get("share_with_org", True):
            return False
        return await ConsentChecker.is_tenant_kg_enabled(db, org_id)

    @staticmethod
    async def get_consent_summary(db, workspace_id: str, org_id: str = None) -> dict:
        return {
            "workspace_kg": await ConsentChecker.is_workspace_kg_enabled(db, workspace_id),
            "tenant_kg": await ConsentChecker.is_tenant_kg_enabled(db, org_id) if org_id else False,
            "platform_kg": await ConsentChecker.is_platform_kg_enabled(db, org_id) if org_id else False,
            "workspace_shares_to_org": await ConsentChecker.can_workspace_share_to_org(db, workspace_id, org_id) if org_id else False,
        }


async def _schedule_kg_purge(db, scope_id: str, scope_type: str):
    await db.kg_purge_jobs.insert_one({
        "job_id": gen_id("kgp"), "scope_id": scope_id, "scope_type": scope_type,
        "status": "pending", "scheduled_at": now_iso(),
        "execute_by": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "executed_at": None, "entities_deleted": 0, "edges_deleted": 0,
    })


async def execute_kg_purge(db, job_id: str):
    job = await db.kg_purge_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job or job["status"] != "pending":
        return
    scope_id = job["scope_id"]
    scope_type = job["scope_type"]
    ent_count = 0
    edge_count = 0
    if scope_type == "workspace":
        r = await db.kg_entities.delete_many({"workspace_id": scope_id})
        ent_count = r.deleted_count
        r2 = await db.kg_edges.delete_many({"workspace_id": scope_id})
        edge_count = r2.deleted_count
    elif scope_type == "tenant":
        r = await db.kg_entities.update_many(
            {"org_id": scope_id, "org_shared": True},
            {"$unset": {"org_shared": "", "org_id": ""}})
        ent_count = r.modified_count
        r2 = await db.kg_edges.delete_many({"org_id": scope_id})
        edge_count = r2.deleted_count
    elif scope_type == "platform":
        org_hash = hashlib.sha256(scope_id.encode()).hexdigest()
        r = await db.kg_platform_entities.delete_many({"source_org_hash": org_hash})
        ent_count = r.deleted_count
    await db.kg_purge_jobs.update_one({"job_id": job_id}, {"$set": {
        "status": "completed", "executed_at": now_iso(),
        "entities_deleted": ent_count, "edges_deleted": edge_count,
    }})


class KnowledgeGraphEngine:
    def __init__(self, db):
        self.db = db

    async def extract_entities_from_message(self, message: dict, channel: dict, workspace_id: str):
        content = message.get("content", "")
        if len(content) < 50 or message.get("sender_type") == "system":
            return []
        # CONSENT GATE — primary enforcement
        if not await ConsentChecker.is_workspace_kg_enabled(self.db, workspace_id):
            return []
        entities = await self._ai_extract(content, workspace_id)
        saved = []
        for entity_data in entities:
            entity = await self._upsert_entity(entity_data, workspace_id, message)
            if entity:
                saved.append(entity)
        await self._build_cooccurrence_edges(saved, workspace_id)
        return saved

    async def _ai_extract(self, text: str, workspace_id: str) -> list:
        from collaboration_core import get_ai_key_for_agent
        from ai_providers import call_ai_direct
        for agent in ["groq", "deepseek", "chatgpt", "gemini", "claude"]:
            api_key, _ = await get_ai_key_for_agent("system", workspace_id, agent)
            if api_key:
                try:
                    result = await call_ai_direct(agent, api_key,
                        "You are a knowledge extraction system. Return ONLY valid JSON.",
                        EXTRACTION_PROMPT.format(text=text[:4000]),
                        workspace_id=workspace_id, db=self.db)
                    from workflow_engine import parse_ai_json
                    parsed = parse_ai_json(result)
                    return parsed.get("entities", [])
                except Exception as e:
                    logger.debug(f"KG extraction failed with {agent}: {e}")
        return []

    async def _upsert_entity(self, entity_data, workspace_id, source_message):
        name = entity_data.get("name", "").strip()
        if not name:
            return None
        entity_id = gen_id("kge")
        tokens = list(set(_tokenize(f"{name} {entity_data.get('description', '')}"[:500])))
        entity = {
            "entity_id": entity_id, "workspace_id": workspace_id,
            "entity_type": entity_data.get("type", "fact"),
            "name": name, "description": entity_data.get("description", ""),
            "content": entity_data.get("content", name),
            "confidence": entity_data.get("confidence", 0.7),
            "source": {
                "type": "conversation",
                "channel_id": source_message.get("channel_id", ""),
                "message_id": source_message.get("message_id", ""),
                "user_id": source_message.get("sender_id", ""),
                "extracted_at": now_iso(),
            },
            "tags": entity_data.get("tags", []),
            "mentions": [], "supersedes": None, "superseded_by": None,
            "is_active": True, "access_count": 0, "last_accessed": None,
            "bm25_tokens": tokens,
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await self.db.kg_entities.insert_one(entity)
        entity.pop("_id", None)
        return entity

    async def _build_cooccurrence_edges(self, entities, workspace_id):
        if len(entities) < 2:
            return
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                # Check for existing edge to boost strength
                existing = await self.db.kg_edges.find_one({
                    "workspace_id": workspace_id,
                    "source_entity_id": entities[i]["entity_id"],
                    "target_entity_id": entities[j]["entity_id"],
                })
                if existing:
                    await self.db.kg_edges.update_one(
                        {"edge_id": existing["edge_id"]},
                        {"$inc": {"strength": 0.1}, "$set": {"updated_at": now_iso()}})
                else:
                    edge = {
                        "edge_id": gen_id("kgr"), "workspace_id": workspace_id,
                        "source_entity_id": entities[i]["entity_id"],
                        "target_entity_id": entities[j]["entity_id"],
                        "relationship": "related_to", "strength": 0.5,
                        "evidence": [], "created_at": now_iso(),
                    }
                    await self.db.kg_edges.insert_one(edge)

    async def add_explicit_edge(self, workspace_id, source_id, target_id, relationship, evidence=""):
        """Add a typed relationship between two entities."""
        VALID_RELS = ["led_to", "replaces", "requires", "contradicts", "supports", "related_to", "owned_by", "part_of"]
        if relationship not in VALID_RELS:
            relationship = "related_to"
        existing = await self.db.kg_edges.find_one({
            "workspace_id": workspace_id,
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "relationship": relationship,
        })
        if existing:
            update = {"$inc": {"strength": 0.15}}
            if evidence:
                update["$push"] = {"evidence": {"excerpt": evidence[:200], "added_at": now_iso()}}
            await self.db.kg_edges.update_one({"edge_id": existing["edge_id"]}, update)
            return existing["edge_id"]
        edge = {
            "edge_id": gen_id("kgr"), "workspace_id": workspace_id,
            "source_entity_id": source_id, "target_entity_id": target_id,
            "relationship": relationship, "strength": 0.6,
            "evidence": [{"excerpt": evidence[:200], "added_at": now_iso()}] if evidence else [],
            "created_at": now_iso(),
        }
        await self.db.kg_edges.insert_one(edge)
        return edge["edge_id"]

    async def supersede_entity(self, workspace_id, old_entity_id, new_entity_id):
        """Mark an entity as superseded by a newer one (decisions evolve)."""
        await self.db.kg_entities.update_one(
            {"entity_id": old_entity_id, "workspace_id": workspace_id},
            {"$set": {"superseded_by": new_entity_id, "is_active": False, "updated_at": now_iso()}})
        await self.db.kg_entities.update_one(
            {"entity_id": new_entity_id, "workspace_id": workspace_id},
            {"$set": {"supersedes": old_entity_id, "updated_at": now_iso()}})
        await self.add_explicit_edge(workspace_id, new_entity_id, old_entity_id, "replaces")

    async def get_entity_neighborhood(self, workspace_id, entity_id, depth=1):
        """Get entity + all connected entities up to N hops."""
        visited = set()
        frontier = {entity_id}
        nodes = []
        edges = []
        for _ in range(depth):
            if not frontier:
                break
            new_frontier = set()
            for eid in frontier:
                if eid in visited:
                    continue
                visited.add(eid)
                entity = await self.db.kg_entities.find_one(
                    {"entity_id": eid, "workspace_id": workspace_id}, {"_id": 0})
                if entity:
                    nodes.append(entity)
                connected_edges = await self.db.kg_edges.find(
                    {"workspace_id": workspace_id, "$or": [
                        {"source_entity_id": eid}, {"target_entity_id": eid}
                    ]}, {"_id": 0}).limit(50).to_list(50)
                for edge in connected_edges:
                    edges.append(edge)
                    other = edge["target_entity_id"] if edge["source_entity_id"] == eid else edge["source_entity_id"]
                    if other not in visited:
                        new_frontier.add(other)
            frontier = new_frontier
        return {"nodes": nodes, "edges": edges}

    async def retrieve_context(self, query: str, workspace_id: str,
                                max_entities: int = 8, max_tokens: int = 2000) -> str:
        # CONSENT GATE
        if not await ConsentChecker.is_workspace_kg_enabled(self.db, workspace_id):
            return ""
        # Tier 1: Workspace-scoped entities
        entities = await self.db.kg_entities.find(
            {"workspace_id": workspace_id, "is_active": True}, {"_id": 0}
        ).sort("access_count", -1).limit(200).to_list(200)
        # Tier 2: Org-wide entities if tenant KG enabled
        ws = await self.db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        org_id = (ws or {}).get("org_id", "")
        if org_id and await ConsentChecker.is_tenant_kg_enabled(self.db, org_id):
            org_entities = await self.db.kg_entities.find(
                {"org_id": org_id, "org_shared": True, "is_active": True,
                 "workspace_id": {"$ne": workspace_id}}, {"_id": 0}
            ).sort("access_count", -1).limit(100).to_list(100)
            entities.extend(org_entities)
        if not entities:
            return ""
        query_tokens = set(_tokenize(query.lower()))
        scored = []
        for e in entities:
            e_tokens = set(e.get("bm25_tokens", []))
            overlap = len(query_tokens & e_tokens)
            if overlap > 0:
                scored.append((e, overlap + e.get("confidence", 0)))
        scored.sort(key=lambda x: x[1], reverse=True)
        context_lines = []
        total_tokens = 0
        for entity, score in scored[:max_entities]:
            text = f"[{entity['entity_type'].upper()}] {entity['name']}: {entity['description']}"
            tokens = len(text.split())
            if total_tokens + tokens > max_tokens:
                break
            context_lines.append(text)
            total_tokens += tokens
            await self.db.kg_entities.update_one(
                {"entity_id": entity["entity_id"]},
                {"$inc": {"access_count": 1}, "$set": {"last_accessed": now_iso()}})
        if not context_lines:
            return ""
        return (
            "\n=== INSTITUTIONAL KNOWLEDGE ===\n"
            "The following is knowledge your organization has accumulated.\n\n"
            + "\n".join(context_lines)
            + "\n=== END KNOWLEDGE ===\n"
        )

    async def create_anonymized_platform_entity(self, entity: dict):
        """Tier 3: Create fully anonymized entity for platform-wide intelligence."""
        org_id = entity.get("org_id", "")
        if not org_id:
            return
        org_hash = hashlib.sha256(org_id.encode()).hexdigest()
        platform_entity = {
            "platform_entity_id": gen_id("kgpe"),
            "entity_type": entity.get("entity_type", "fact"),
            "category_tags": entity.get("tags", [])[:5],
            "source_org_hash": org_hash,
            "created_at": now_iso(),
        }
        await self.db.kg_platform_entities.insert_one(platform_entity)
