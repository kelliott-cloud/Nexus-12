"""Centralized Key Resolution — Single source of truth for all integration keys.

Resolves keys from three sources in priority order:
1. Org-level encrypted override (org_integrations collection)
2. Platform settings (platform_settings collection, saved via Integration Settings UI)
3. Environment variables (set at process startup)

This fixes the disconnect where Integration Settings saved keys to platform_settings
but all routes only read from os.environ.get().
"""
import os
import logging

logger = logging.getLogger(__name__)

# Cache to avoid repeated DB queries for the same key within a request
_cache = {}
_CACHE_TTL = 60  # seconds
import time as _time


async def get_integration_key(db, key_name: str, org_id: str = None, user_id: str = None) -> str:
    """Resolve an integration key from org override → managed keys → platform_settings → env var.
    
    Args:
        db: MongoDB database instance
        key_name: The key name (e.g., 'GITHUB_CLIENT_ID', 'STRIPE_API_KEY')
        org_id: Optional org ID for org-level overrides
        user_id: Optional user ID for managed key resolution
    
    Returns:
        The key value, or empty string if not found
    """
    cache_key = f"{org_id or ''}:{user_id or ''}:{key_name}"
    cached = _cache.get(cache_key)
    if cached and (_time.time() - cached[1]) < _CACHE_TTL:
        return cached[0]

    value = ""

    # 1. Check org-level override (encrypted)
    if org_id:
        try:
            override = await db.org_integrations.find_one(
                {"org_id": org_id, "key": key_name}, {"_id": 0}
            )
            if override and override.get("value_encrypted"):
                from encryption import get_fernet; fernet = get_fernet()
                value = fernet.decrypt(override["value_encrypted"].encode()).decode()
            elif override and override.get("value"):
                value = override["value"]
        except Exception as e:
            logger.debug(f"Org key resolution failed for {key_name}: {e}")

    # 2. Check managed keys (platform keys shared with tenants)
    if not value and user_id:
        try:
            from managed_keys import INTEGRATION_KEY_MAP, is_user_opted_in, _db as mk_db
            for integration, key_names_list in INTEGRATION_KEY_MAP.items():
                if key_name in key_names_list:
                    if await is_user_opted_in(user_id, integration):
                        settings = await db.platform_settings.find_one(
                            {"setting_id": "managed_keys"}, {"_id": 0})
                        if settings:
                            stored = (settings.get("keys") or {}).get(f"{integration}:{key_name}")
                            if stored:
                                try:
                                    from encryption import get_fernet; fernet = get_fernet()
                                    value = fernet.decrypt(stored.encode()).decode()
                                except Exception as _e:
                                    import logging; logging.getLogger("key_resolver").warning(f"Suppressed: {_e}")
                    break
        except Exception as e:
            logger.debug(f"Managed key check failed for {key_name}: {e}")

    # 3. Check platform_settings (saved via Integration Settings UI)
    if not value:
        try:
            setting = await db.platform_settings.find_one(
                {"key": key_name}, {"_id": 0}
            )
            if setting and setting.get("value"):
                value = setting["value"]
        except Exception as e:
            logger.debug(f"Platform settings lookup failed for {key_name}: {e}")

    # 4. Fall back to environment variable
    if not value:
        value = os.environ.get(key_name, "")

    _cache[cache_key] = (value, _time.time())
    return value


def clear_cache():
    """Clear the key resolution cache (call after saving new keys)."""
    _cache.clear()
