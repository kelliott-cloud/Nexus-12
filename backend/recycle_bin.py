"""Recycle Bin — Soft-delete system for projects, tasks, milestones, artifacts, and repo files.

Deleted items are moved to `recycle_bin` collection and marked as deleted in their original collection.
AI agents cannot see or access deleted items. Only ORG admins can view and purge the recycle bin.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


async def soft_delete(db, collection_name: str, id_field: str, id_value: str,
                      workspace_id: str, deleted_by: str, deleted_by_name: str):
    """Soft-delete an item: move to recycle bin + mark as deleted in original collection."""
    collection = getattr(db, collection_name)
    item = await collection.find_one({id_field: id_value}, {"_id": 0})
    if not item:
        return None

    # Save to recycle bin
    bin_entry = {
        "bin_id": f"bin_{uuid.uuid4().hex[:12]}",
        "collection": collection_name,
        "id_field": id_field,
        "id_value": id_value,
        "workspace_id": workspace_id,
        "original_data": item,
        "deleted_by": deleted_by,
        "deleted_by_name": deleted_by_name,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "purged": False,
    }
    await db.recycle_bin.insert_one(bin_entry)

    # Mark as deleted in original collection (soft delete)
    await collection.update_one(
        {id_field: id_value},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": deleted_by}}
    )

    logger.info(f"Soft-deleted {collection_name}.{id_field}={id_value} by {deleted_by_name}")
    return bin_entry["bin_id"]


async def restore_item(db, bin_id: str):
    """Restore a soft-deleted item from the recycle bin."""
    entry = await db.recycle_bin.find_one({"bin_id": bin_id, "purged": False}, {"_id": 0})
    if not entry:
        return False

    collection = getattr(db, entry["collection"])
    # Remove the is_deleted flag
    await collection.update_one(
        {entry["id_field"]: entry["id_value"]},
        {"$unset": {"is_deleted": "", "deleted_at": "", "deleted_by": ""}}
    )
    # Mark bin entry as restored
    await db.recycle_bin.delete_one({"bin_id": bin_id})
    logger.info(f"Restored {entry['collection']}.{entry['id_field']}={entry['id_value']}")
    return True


async def purge_item(db, bin_id: str):
    """Permanently delete an item from the recycle bin (ORG admin only)."""
    entry = await db.recycle_bin.find_one({"bin_id": bin_id, "purged": False}, {"_id": 0})
    if not entry:
        return False

    collection = getattr(db, entry["collection"])
    # Permanently delete from original collection
    await collection.delete_one({entry["id_field"]: entry["id_value"]})
    # Mark as purged
    await db.recycle_bin.update_one({"bin_id": bin_id}, {"$set": {"purged": True, "purged_at": datetime.now(timezone.utc).isoformat()}})
    logger.info(f"Purged {entry['collection']}.{entry['id_field']}={entry['id_value']}")
    return True


def register_recycle_bin_routes(api_router, db, get_current_user):
    """Admin-only endpoints for managing the recycle bin."""

    @api_router.get("/admin/recycle-bin")
    async def get_recycle_bin(request: Request, workspace_id: str = None, collection: str = None, limit: int = 50):
        """Get recycle bin contents (admin only)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            org_admin = await db.org_memberships.find_one(
                {"user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
            )
            if not org_admin:
                raise HTTPException(403, "Admin access required")

        query = {"purged": False}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if collection:
            query["collection"] = collection

        items = await db.recycle_bin.find(query, {"_id": 0}).sort("deleted_at", -1).limit(limit).to_list(limit)
        total = await db.recycle_bin.count_documents(query)
        return {"items": items, "total": total}

    @api_router.post("/admin/recycle-bin/{bin_id}/restore")
    async def restore_bin_item(bin_id: str, request: Request):
        """Restore a deleted item (admin only)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        ok = await restore_item(db, bin_id)
        if not ok:
            raise HTTPException(404, "Item not found in recycle bin")
        return {"restored": True, "bin_id": bin_id}

    @api_router.delete("/admin/recycle-bin/{bin_id}")
    async def purge_bin_item(bin_id: str, request: Request):
        """Permanently delete an item (admin only, no undo)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        ok = await purge_item(db, bin_id)
        if not ok:
            raise HTTPException(404, "Item not found in recycle bin")
        return {"purged": True, "bin_id": bin_id}

    @api_router.delete("/admin/recycle-bin")
    async def purge_all(request: Request, workspace_id: str = None, collection: str = None):
        """Purge all items in the recycle bin (admin only)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        query = {"purged": False}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if collection:
            query["collection"] = collection
        items = await db.recycle_bin.find(query, {"_id": 0, "bin_id": 1}).to_list(500)
        count = 0
        for item in items:
            if await purge_item(db, item["bin_id"]):
                count += 1
        return {"purged_count": count}

    @api_router.post("/admin/recycle-bin/bulk-restore")
    async def bulk_restore(request: Request):
        """Restore multiple items at once (admin only)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        body = await request.json()
        bin_ids = body.get("bin_ids") or []
        if not bin_ids:
            raise HTTPException(400, "bin_ids required")
        restored = 0
        errors = []
        for bid in bin_ids:
            try:
                ok = await restore_item(db, bid)
                if ok:
                    restored += 1
                else:
                    errors.append({"bin_id": bid, "error": "Not found"})
            except Exception as e:
                errors.append({"bin_id": bid, "error": str(e)[:100]})
        return {"restored": restored, "errors": errors}

    @api_router.post("/admin/recycle-bin/bulk-purge")
    async def bulk_purge(request: Request):
        """Permanently delete multiple items at once (admin only)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        body = await request.json()
        bin_ids = body.get("bin_ids") or []
        if not bin_ids:
            raise HTTPException(400, "bin_ids required")
        purged = 0
        errors = []
        for bid in bin_ids:
            try:
                ok = await purge_item(db, bid)
                if ok:
                    purged += 1
                else:
                    errors.append({"bin_id": bid, "error": "Not found"})
            except Exception as e:
                errors.append({"bin_id": bid, "error": str(e)[:100]})
        return {"purged": purged, "errors": errors}

    @api_router.get("/admin/recycle-bin/types")
    async def get_recycle_bin_types(request: Request):
        """Get distinct item types in the recycle bin for filtering."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        pipeline = [
            {"$match": {"purged": False}},
            {"$group": {"_id": "$collection", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        types = []
        async for doc in db.recycle_bin.aggregate(pipeline):
            types.append({"type": doc["_id"], "count": doc["count"]})
        return {"types": types}
