"""Knowledge Graph Hooks — Wire ambient learning into existing flows. ALL hooks enforce ConsentChecker."""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def on_message_created(db, message: dict, channel: dict, workspace_id: str):
    try:
        from knowledge_graph import KnowledgeGraphEngine, ConsentChecker
        if not await ConsentChecker.is_workspace_kg_enabled(db, workspace_id):
            return
        kg = KnowledgeGraphEngine(db)
        entities = await kg.extract_entities_from_message(message, channel, workspace_id)
        # Tier 2: Tag for org sharing if double-gate passes
        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        org_id = (ws or {}).get("org_id", "")
        if org_id and await ConsentChecker.can_workspace_share_to_org(db, workspace_id, org_id):
            for entity in entities:
                await db.kg_entities.update_one(
                    {"entity_id": entity["entity_id"]},
                    {"$set": {"org_shared": True, "org_id": org_id}})
        # Tier 3: Create anonymized copy if platform KG enabled
        if org_id and await ConsentChecker.is_platform_kg_enabled(db, org_id):
            for entity in entities:
                entity["org_id"] = org_id
                await kg.create_anonymized_platform_entity(entity)
    except Exception as e:
        logger.debug(f"KG hook (message) failed: {e}")


async def on_wiki_page_saved(db, page: dict, workspace_id: str):
    try:
        from knowledge_graph import KnowledgeGraphEngine, ConsentChecker
        if not await ConsentChecker.is_workspace_kg_enabled(db, workspace_id):
            return
        kg = KnowledgeGraphEngine(db)
        fake_msg = {"content": f"{page.get('title','')}: {page.get('content','')[:2000]}",
                    "channel_id": "", "message_id": page.get("page_id", ""),
                    "sender_id": page.get("updated_by", ""), "sender_type": "human"}
        asyncio.create_task(kg.extract_entities_from_message(fake_msg, {}, workspace_id))
    except Exception as e:
        logger.debug(f"KG hook (wiki) failed: {e}")


async def on_task_completed(db, task: dict, workspace_id: str):
    try:
        from knowledge_graph import KnowledgeGraphEngine, ConsentChecker
        if not await ConsentChecker.is_workspace_kg_enabled(db, workspace_id):
            return
        kg = KnowledgeGraphEngine(db)
        fake_msg = {"content": f"Task completed: {task.get('title','')}. {task.get('description','')}",
                    "channel_id": "", "message_id": task.get("task_id", ""),
                    "sender_id": task.get("assigned_to", ""), "sender_type": "human"}
        asyncio.create_task(kg.extract_entities_from_message(fake_msg, {}, workspace_id))
    except Exception as e:
        logger.debug(f"KG hook (task) failed: {e}")
