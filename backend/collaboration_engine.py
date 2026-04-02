"""Nexus Collaboration Engine — Shared state and utilities for AI collaboration.

Manages the collaboration lifecycle: active sessions, persist state,
hard stop signals, pending batches, and human priority queues.

Extracted from server.py to reduce monolith size and improve testability.
"""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ============ Shared State ============
# These are the global state dictionaries that the collaboration system uses.
# They're defined here so any module can import and reference them.

# Active collaboration flags: "{channel_id}_running" -> True, "{channel_id}_{agent_key}" -> "thinking"
active_collaborations = {}

# Persist session state: channel_id -> {enabled, round, delay, ...}
persist_sessions = {}

# Auto-collab session state: channel_id -> {round, max_rounds, ...}
auto_collab_sessions = {}

# Hard stop signal: channel_id -> True means "stop immediately, batch pending work"
hard_stop = {}

# Pending work batch: channel_id -> [messages that were in-flight when stopped]
pending_batch = {}

# Human priority queue: channel_id -> {pause_requested, message, user_id, ...}
human_priority = defaultdict(dict)


def get_collaboration_status(channel_id: str):
    """Get the current collaboration status for a channel."""
    is_running = active_collaborations.get(f"{channel_id}_running", False)
    persist = persist_sessions.get(channel_id, {})
    auto = auto_collab_sessions.get(channel_id, {})
    
    # Gather agent-level status
    agents = {}
    for key, val in active_collaborations.items():
        if key.startswith(f"{channel_id}_") and not key.endswith("_running"):
            agent_key = key.replace(f"{channel_id}_", "")
            agents[agent_key] = val
    
    return {
        "is_running": is_running,
        "agents": agents,
        "persist_enabled": persist.get("enabled", False),
        "persist_round": persist.get("round", 0),
        "auto_collab_active": auto.get("enabled", False),
        "hard_stopped": hard_stop.get(channel_id, False),
        "pending_batch_count": len(pending_batch.get(channel_id, [])),
    }
