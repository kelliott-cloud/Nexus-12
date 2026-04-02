"""Instance Registry — Persistent per-deployment UUID for record tracing.

Every document inserted into MongoDB automatically gets an `instance_id` field,
allowing you to trace which deployment instance created each record.

The instance UUID is generated once and persisted in the `nexus_instance_registry`
collection. It survives server restarts.
"""
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_instance_id: str = ""

# Collections that should NOT get instance_id injected (internal/system collections)
_SKIP_COLLECTIONS = {"nexus_instance_registry"}


def get_instance_id() -> str:
    return _instance_id


async def init_instance_id(raw_db) -> str:
    """Load or create the persistent instance UUID from the database.
    Uses raw_db (unpatched) to avoid circular issues."""
    global _instance_id

    coll = raw_db["nexus_instance_registry"]
    doc = await coll.find_one({"type": "instance"}, {"_id": 0})
    if doc and doc.get("instance_id"):
        _instance_id = doc["instance_id"]
        logger.info(f"Loaded existing instance ID: {_instance_id}")
    else:
        _instance_id = f"inst_{uuid.uuid4().hex}"
        await coll.insert_one({
            "type": "instance",
            "instance_id": _instance_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Generated new instance ID: {_instance_id}")

    return _instance_id


def wrap_collection(collection):
    """Wrap a single collection's insert methods to auto-inject instance_id."""
    if getattr(collection, "_instance_patched", False):
        return collection
    if collection.name in _SKIP_COLLECTIONS:
        return collection

    _orig_insert_one = collection.insert_one
    _orig_insert_many = collection.insert_many

    async def patched_insert_one(document, *args, **kwargs):
        if isinstance(document, dict) and "instance_id" not in document:
            document["instance_id"] = _instance_id
        return await _orig_insert_one(document, *args, **kwargs)

    async def patched_insert_many(documents, *args, **kwargs):
        if isinstance(documents, list):
            for doc in documents:
                if isinstance(doc, dict) and "instance_id" not in doc:
                    doc["instance_id"] = _instance_id
        return await _orig_insert_many(documents, *args, **kwargs)

    collection.insert_one = patched_insert_one
    collection.insert_many = patched_insert_many
    collection._instance_patched = True
    return collection
