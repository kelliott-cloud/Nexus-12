# Collaboration Engine — Extraction Guide

## Current State
The collaboration code in `server.py` spans ~1400 lines across these functions:
- `run_ai_collaboration()` — Main orchestration (lines 291-410)
- `run_single_agent()` — Inner function with AI calls, tools, context (lines 398-1080)
- Route handlers for `/collaborate`, `/persist`, `/auto-collab`, `/human-priority`
- `run_persist_collaboration()` and `run_auto_collaboration_loop()`

## Why It Can't Be Extracted Simply
1. `run_single_agent` is a **nested function** inside `run_ai_collaboration` — it captures `db`, `AI_MODELS`, `ws_manager`, `channel`, `user_id`, `messages`, and `context_snapshot` via closure
2. Route handlers (`@api_router.post("/channels/{channel_id}/collaborate")`) require `api_router` and `db` from server.py scope
3. The functions reference 15+ global/shared state dicts from `collaboration_engine.py`

## Recommended Extraction Path (for future refactoring)
1. Convert `run_single_agent` to accept all dependencies as parameters (not closures)
2. Move it to `collaboration_core.py` as a standalone async function
3. Keep route handlers in server.py (they're thin wrappers)
4. Move `run_persist_collaboration` and `run_auto_collaboration_loop` to a separate module
5. Use dependency injection pattern instead of global imports

## Shared State (already extracted)
- `collaboration_engine.py` — active_collaborations, persist_sessions, etc.
- `state.py` — Redis-backed state abstraction
- `nexus_config.py` — AI_MODELS, CODE_REPO_PROMPT
