from nexus_utils import now_iso
"""Keystone Architecture — Event Bus, Circuit Breaker, Billing Enforcement,
Cost Arbitrage, Consensus Engine, GDPR Erasure, Key Rotation."""
import uuid
import time
import re
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)



# ============ B1: Event Bus ============

class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)

    def on(self, event_type, handler):
        self._handlers[event_type].append(handler)

    async def emit(self, event_type, payload):
        payload["event_type"] = event_type
        payload["timestamp"] = now_iso()
        for handler in self._handlers.get(event_type, []):
            try:
                asyncio.create_task(self._safe_call(handler, payload, event_type))
            except Exception as e:
                logger.debug(f"Event handler scheduling error for {event_type}: {e}")
        for handler in self._handlers.get("*", []):
            try:
                asyncio.create_task(self._safe_call(handler, payload, event_type))
            except Exception as _e:
                import logging; logging.getLogger("keystone").warning(f"Suppressed: {_e}")

    async def _safe_call(self, handler, payload, event_type):
        try:
            await asyncio.wait_for(handler(payload), timeout=30)
        except asyncio.TimeoutError:
            logger.warning(f"Event handler for {event_type} timed out (30s)")
        except Exception as e:
            logger.warning(f"Event handler for {event_type} failed: {e}")


# Global instance
event_bus = EventBus()


# ============ B4: Provider Circuit Breaker ============

class ProviderCircuitBreaker:
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60
    HALF_OPEN_MAX = 2

    def __init__(self):
        self._state = {}

    def _get_state(self, provider):
        if provider not in self._state:
            self._state[provider] = {"state": "closed", "failures": 0, "last_failure": 0, "opened_at": 0, "half_open_attempts": 0}
        return self._state[provider]

    def is_available(self, provider):
        s = self._get_state(provider)
        if s["state"] == "closed":
            return True
        if s["state"] == "open":
            if time.time() - s["opened_at"] > self.RECOVERY_TIMEOUT:
                s["state"] = "half_open"
                s["half_open_attempts"] = 0
                return True
            return False
        if s["state"] == "half_open":
            return s["half_open_attempts"] < self.HALF_OPEN_MAX
        return True

    def record_success(self, provider):
        s = self._get_state(provider)
        s["failures"] = 0
        s["state"] = "closed"

    def record_failure(self, provider):
        s = self._get_state(provider)
        s["failures"] += 1
        s["last_failure"] = time.time()
        if s["failures"] >= self.FAILURE_THRESHOLD:
            s["state"] = "open"
            s["opened_at"] = time.time()
            logger.warning(f"Circuit OPEN for {provider} after {s['failures']} failures")

    async def call_with_breaker(self, provider, call_fn):
        if not self.is_available(provider):
            raise Exception(f"Provider {provider} circuit is OPEN. Try again in {self.RECOVERY_TIMEOUT}s.")
        try:
            result = await call_fn()
            self.record_success(provider)
            return result
        except Exception as e:
            self.record_failure(provider)
            raise

    def get_status(self):
        return {p: {"state": s["state"], "failures": s["failures"]} for p, s in self._state.items()}


circuit_breaker = ProviderCircuitBreaker()


# ============ B2: Billing Enforcement ============

METERED_ACTIONS = {
    "ai_collaboration": {"free": 50, "starter": 500, "pro": 5000, "team": -1, "enterprise": -1},
    "image_generation": {"free": 5, "starter": 50, "pro": 500, "team": -1, "enterprise": -1},
    "pipeline_execution": {"free": 5, "starter": 50, "pro": 500, "team": -1, "enterprise": -1},
    "agent_training": {"free": 2, "starter": 20, "pro": 200, "team": -1, "enterprise": -1},
    "code_execution": {"free": 10, "starter": 100, "pro": 1000, "team": -1, "enterprise": -1},
    "file_upload_mb": {"free": 50, "starter": 500, "pro": 5000, "team": -1, "enterprise": -1},
    "research_queries": {"free": 5, "starter": 50, "pro": 500, "team": -1, "enterprise": -1},
    "operator_sessions": {"free": 2, "starter": 20, "pro": 200, "team": -1, "enterprise": -1},
}


async def check_usage(db, user_id, action):
    if action not in METERED_ACTIONS:
        return True
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "plan": 1, "usage": 1})
    if not user:
        return False
    plan = user.get("plan", "free")
    limits = METERED_ACTIONS[action]
    limit = limits.get(plan, limits.get("free", 0))
    if limit == -1:
        return True
    usage = user.get("usage") or {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if usage.get("reset_date") != today:
        reset_fields = {"usage.reset_date": today}
        for action_key in METERED_ACTIONS:
            reset_fields[f"usage.{action_key}"] = 0
        await db.users.update_one({"user_id": user_id}, {"$set": reset_fields})
        return True
    current = usage.get(action, 0)
    return current < limit


async def increment_usage(db, user_id, action):
    await db.users.update_one({"user_id": user_id}, {"$inc": {f"usage.{action}": 1}})


# ============ A3: Cost Arbitrage (Phase 1 — Rule-based) ============

TASK_PATTERNS = {
    "code_generation": [r"write.*code", r"implement", r"create.*function", r"build.*component", r"generate.*class"],
    "code_review": [r"review.*code", r"check.*bug", r"find.*issue", r"audit.*security"],
    "creative_writing": [r"write.*story", r"blog.*post", r"creative", r"draft.*email", r"marketing.*copy"],
    "factual_qa": [r"what is", r"explain", r"how does", r"define", r"compare"],
    "summarization": [r"summarize", r"tldr", r"key points", r"brief.*overview"],
    "data_analysis": [r"analyze.*data", r"statistics", r"trend", r"calculate", r"forecast"],
    "debugging": [r"debug", r"error.*fix", r"not working", r"stack trace", r"exception"],
}

MODEL_COSTS = {
    "deepseek": 0.0003, "mistral": 0.002, "gemini": 0.0001, "cohere": 0.001,
    "chatgpt": 0.005, "claude": 0.003, "grok": 0.005, "perplexity": 0.001,
}

MODEL_QUALITY = {
    "code_generation": {"claude": 0.95, "chatgpt": 0.92, "deepseek": 0.88, "gemini": 0.82, "mistral": 0.78},
    "code_review": {"claude": 0.94, "chatgpt": 0.90, "deepseek": 0.85, "gemini": 0.80},
    "creative_writing": {"claude": 0.93, "chatgpt": 0.95, "gemini": 0.82, "mistral": 0.75},
    "factual_qa": {"chatgpt": 0.90, "claude": 0.92, "gemini": 0.88, "deepseek": 0.80, "perplexity": 0.93},
    "summarization": {"claude": 0.92, "chatgpt": 0.90, "gemini": 0.88, "deepseek": 0.82, "mistral": 0.80},
    "data_analysis": {"claude": 0.90, "chatgpt": 0.88, "deepseek": 0.85, "gemini": 0.82},
    "debugging": {"claude": 0.93, "chatgpt": 0.90, "deepseek": 0.87, "gemini": 0.80},
}


def classify_task(prompt):
    prompt_lower = prompt.lower()
    for task_type, patterns in TASK_PATTERNS.items():
        for p in patterns:
            if re.search(p, prompt_lower):
                return task_type
    complexity = "high" if len(prompt) > 2000 else "medium" if len(prompt) > 500 else "low"
    return f"general_{complexity}"


def select_cheapest_model(task_type, enabled_models, quality_threshold=0.7):
    quality_map = MODEL_QUALITY.get(task_type, {})
    candidates = []
    for model in enabled_models:
        quality = quality_map.get(model, 0.7)
        cost = MODEL_COSTS.get(model, 0.005)
        if quality >= quality_threshold:
            candidates.append((model, quality, cost))
    candidates.sort(key=lambda x: x[2])
    if candidates:
        return candidates[0][0], candidates[0][1], candidates[0][2]
    return enabled_models[0] if enabled_models else "chatgpt", 0.7, 0.005


# ============ B3: GDPR Erasure ============

USER_DATA_COLLECTIONS = [
    ("user_sessions", "user_id", "delete"),
    ("login_attempts", "email", "delete"),
    ("notifications", "user_id", "delete"),
    ("ai_call_logs", "user_id", "anonymize"),
    ("messages", "sender_id", "anonymize"),
    ("bridge_tokens", "user_id", "delete"),
    ("developer_api_keys", "user_id", "delete"),
    ("agent_marketplace", "publisher_id", "anonymize"),
    ("workspace_members", "user_id", "delete"),
    ("cursor_sessions", "user_id", "anonymize"),
    ("openclaw_sessions", "sender_id", "anonymize"),
]


async def erase_user(db, user_id, reason="user_request"):
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user:
        return {"error": "User not found"}
    erased = []
    for collection, field, action in USER_DATA_COLLECTIONS:
        try:
            if action == "delete":
                r = await db[collection].delete_many({field: user_id})
                erased.append({"collection": collection, "action": "deleted", "count": r.deleted_count})
            elif action == "anonymize":
                r = await db[collection].update_many({field: user_id}, {"$set": {field: None, "sender_name": "Deleted User"}})
                erased.append({"collection": collection, "action": "anonymized", "count": r.modified_count})
        except Exception as e:
            erased.append({"collection": collection, "action": "error", "error": str(e)[:100]})

    # Anonymize the user record itself
    await db.users.update_one({"user_id": user_id}, {"$set": {
        "email": f"deleted_{user_id}@erased.nexus", "name": "Deleted User",
        "picture": "", "password_hash": None, "ai_keys": {},
        "erased_at": now_iso(), "erased_reason": reason,
    }})
    erased.append({"collection": "users", "action": "anonymized", "count": 1})

    # Audit log (log the erasure, not the data)
    await db.audit_log.insert_one({
        "action": "gdpr_erasure", "user_id": "system",
        "resource_type": "user", "resource_id": user_id,
        "details": {"reason": reason, "collections_processed": len(erased)},
        "timestamp": now_iso(),
    })
    return {"erased": erased, "user_id": user_id}


# ============ B5: API Key Rotation & Expiry ============

async def check_key_expiry(db, key_doc):
    expires_at = key_doc.get("expires_at")
    if not expires_at:
        return True
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    return expires_at > datetime.now(timezone.utc)


async def rotate_key(db, key_id, user_id):
    import secrets, hashlib
    from routes.routes_ai_keys import encrypt_key
    old_key = await db.developer_api_keys.find_one({"key_id": key_id, "user_id": user_id}, {"_id": 0})
    if not old_key:
        return None
    # Mark old key as deprecated with 24h grace
    await db.developer_api_keys.update_one({"key_id": key_id}, {"$set": {
        "status": "deprecated",
        "deprecated_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
    }})
    # Create new key
    raw = f"nxapi_{secrets.token_urlsafe(48)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    new_doc = {
        "key_id": f"apk_{uuid.uuid4().hex[:12]}", "user_id": user_id,
        "key_hash": key_hash, "key_prefix": raw[:12],
        "label": f"{old_key.get('label', 'API Key')} (rotated)",
        "workspace_id": old_key.get("workspace_id", ""),
        "permissions": old_key.get("permissions", ["read", "write", "ai"]),
        "rate_limit": old_key.get("rate_limit", 60),
        "status": "active",
        "created_at": now_iso(), "last_used_at": None,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        "revoked": False, "rotated_from": key_id,
    }
    await db.developer_api_keys.insert_one(new_doc)
    new_doc.pop("_id", None)
    new_doc["key"] = raw
    new_doc.pop("key_hash", None)
    return new_doc
