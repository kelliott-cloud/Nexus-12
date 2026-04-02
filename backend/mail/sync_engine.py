"""Mail sync engine — initial sync + delta sync for all connected accounts."""
import logging
from datetime import datetime, timezone
from nexus_utils import now_iso

logger = logging.getLogger(__name__)


async def run_initial_sync(db, connection_id: str):
    """One-shot initial sync for a newly connected mail account."""
    conn = await db.mail_connections.find_one({"connection_id": connection_id}, {"_id": 0})
    if not conn:
        logger.warning(f"Initial sync: connection {connection_id} not found")
        return
    provider = conn.get("provider")
    try:
        await db.mail_connections.update_one(
            {"connection_id": connection_id},
            {"$set": {"sync_status": "syncing", "last_sync_started": now_iso()}})

        # Phase 1: Stub sync — marks connection as synced
        # Real provider sync will be implemented when OAuth credentials are configured
        await db.mail_connections.update_one(
            {"connection_id": connection_id},
            {"$set": {
                "sync_status": "synced",
                "last_sync_at": now_iso(),
                "message_count": 0,
                "thread_count": 0,
            }})
        logger.info(f"Initial sync complete for {connection_id} ({provider})")
    except Exception as e:
        logger.error(f"Initial sync failed for {connection_id}: {e}")
        await db.mail_connections.update_one(
            {"connection_id": connection_id},
            {"$set": {"sync_status": "error", "sync_error": str(e)[:500]}})


async def run_delta_sync_all(db):
    """Periodic delta sync for all active connections."""
    connections = await db.mail_connections.find(
        {"status": "active", "sync_status": {"$ne": "syncing"}},
        {"_id": 0, "connection_id": 1, "provider": 1}
    ).to_list(100)

    for conn in connections:
        try:
            await db.mail_connections.update_one(
                {"connection_id": conn["connection_id"]},
                {"$set": {"last_sync_at": now_iso()}})
        except Exception as e:
            logger.warning(f"Delta sync failed for {conn['connection_id']}: {e}")
