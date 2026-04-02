"""Dojo Integration Patches — Exact changes to existing Nexus 7.0 files.

This file documents the minimal surgical changes needed to wire Agent Dojo
into the existing codebase. Each section shows the file, the insertion point,
and the exact code to add.

Run order:
  1. Drop dojo_engine.py, dojo_prompts.py, dojo_data_extractor.py,
     dojo_scenarios.py into backend/
  2. Drop routes_dojo.py into backend/routes/
  3. Apply patches below
  4. Run db_indexes migration
"""


# ================================================================
# PATCH 1: backend/server.py
# Insert after the last register_*_routes() call block
# ================================================================

SERVER_PY_PATCH = '''
# --- Agent Dojo Module ---
from routes.routes_dojo import register_dojo_routes
register_dojo_routes(api_router, db, get_current_user)

from dojo_engine import DojoEngine
dojo_engine = DojoEngine(db, ws_manager)
'''


# ================================================================
# PATCH 2: backend/routes/__init__.py
# Add to the import list (alphabetical position after routes_directive_engine)
# ================================================================

ROUTES_INIT_PATCH = '''from routes.routes_dojo import *  # noqa: F401,F403'''


# ================================================================
# PATCH 3: backend/db_indexes.py
# Add to the ensure_indexes() function
# ================================================================

DB_INDEXES_PATCH = '''
    # --- Agent Dojo indexes ---
    await db.dojo_sessions.create_index(
        [("workspace_id", 1), ("status", 1), ("created_at", -1)],
        name="dojo_sessions_ws_status_date"
    )
    await db.dojo_sessions.create_index(
        [("session_id", 1)],
        unique=True,
        name="dojo_sessions_id_unique"
    )
    await db.dojo_sessions.create_index(
        [("workspace_id", 1), ("agents.agent_id", 1)],
        name="dojo_sessions_ws_agent"
    )
    await db.dojo_scenarios.create_index(
        [("scenario_id", 1)],
        unique=True,
        name="dojo_scenarios_id_unique"
    )
    await db.dojo_scenarios.create_index(
        [("workspace_id", 1), ("category", 1)],
        name="dojo_scenarios_ws_category"
    )
    await db.dojo_scenarios.create_index(
        [("is_builtin", 1), ("category", 1)],
        name="dojo_scenarios_builtin_category"
    )
    await db.dojo_extracted_data.create_index(
        [("extraction_id", 1)],
        unique=True,
        name="dojo_extracted_id_unique"
    )
    await db.dojo_extracted_data.create_index(
        [("session_id", 1), ("status", 1)],
        name="dojo_extracted_session_status"
    )
    await db.dojo_extracted_data.create_index(
        [("agent_id", 1), ("workspace_id", 1)],
        name="dojo_extracted_agent_ws"
    )
'''


# ================================================================
# PATCH 4: backend/agent_evaluator.py
# Add after the existing skill assessment loop (inside run_real_assessment)
# This allows Dojo transcripts to count as assessment evidence
# ================================================================

AGENT_EVALUATOR_PATCH = '''
    # --- Dojo Session Assessment Evidence ---
    # Check if agent has completed Dojo sessions that align with assessed skills
    try:
        for skill_config in to_assess:
            skill_id = skill_config.get("skill_id")
            dojo_sessions = await db.dojo_sessions.find(
                {
                    "workspace_id": workspace_id,
                    "agents.agent_id": agent_id,
                    "status": "completed",
                },
                {"_id": 0, "synthetic_data": 1, "scenario_id": 1}
            ).limit(10).to_list(10)

            for ds in dojo_sessions:
                # Check if this session's scenario aligns with the skill
                scenario_id = ds.get("scenario_id", "")
                from dojo_scenarios import get_scenario
                scenario = get_scenario(scenario_id)
                if scenario and skill_id in scenario.get("skill_alignment", []):
                    quality = (ds.get("synthetic_data") or {}).get("quality_avg", 0)
                    if quality > 0.6:
                        # Boost skill score based on Dojo performance
                        current = skill_scores.get(skill_id, {}).get("score", 0)
                        dojo_bonus = min(10, int(quality * 15))
                        skill_scores[skill_id] = {
                            **skill_scores.get(skill_id, {}),
                            "score": min(100, current + dojo_bonus),
                            "dojo_evidence": True,
                            "dojo_sessions_count": len(dojo_sessions),
                        }
    except Exception as e:
        logger.debug(f"Dojo assessment evidence check: {e}")
'''


# ================================================================
# PATCH 5: backend/smart_routing.py
# Add new function for Dojo phase-aware routing
# ================================================================

SMART_ROUTING_PATCH = '''
def get_dojo_optimal_model(turn_number: int, max_turns: int,
                            available_models: list) -> str:
    """Phase-aware model selection for Dojo sessions.

    Exploration (early) → cheap models
    Development (middle) → standard models
    Convergence (late) → premium models
    Validation (final 2) → cross-model (different from last speaker)
    """
    progress = turn_number / max(max_turns, 1)

    if progress < 0.2:
        tier = "light"      # Turns 1-10 of 50: Groq, DeepSeek
    elif progress < 0.6:
        tier = "standard"   # Turns 11-30: GPT, Gemini
    elif progress < 0.95:
        tier = "premium"    # Turns 31-47: Claude
    else:
        tier = "standard"   # Final 2-3 turns: cross-validate

    return get_optimal_model("", available_models, force_tier=tier)
'''


# ================================================================
# PATCH 6: backend/conversation_learning.py
# In extract_knowledge_from_feedback(), boost weight for Dojo sources
# Add after the chunk is built, before inserting into agent_knowledge
# ================================================================

CONVERSATION_LEARNING_PATCH = '''
    # Boost quality score if this knowledge originated from a Dojo session
    source = chunk.get("source", {})
    if source.get("type") == "dojo_session":
        chunk["quality_score"] = min(1.0, chunk.get("quality_score", 0.5) * 1.2)
        chunk["dojo_validated"] = True
'''


# ================================================================
# PATCH 7: backend/routes/routes_arena.py
# Add 'dojo_roleplay' to the leaderboard categories
# In get_leaderboard(), after the existing category filter
# ================================================================

ARENA_PATCH = '''
    # Dojo Battle Mode: compare scenario outcomes across model pairings
    @api_router.post("/workspaces/{ws_id}/arena/dojo-battle")
    async def create_dojo_battle(ws_id: str, request: Request):
        """Run same Dojo scenario with different model pairings."""
        user = await get_current_user(request)
        body = await request.json()
        scenario_id = body.get("scenario_id", "")
        pairings = body.get("pairings", [])  # e.g., [["claude","chatgpt"], ["gemini","deepseek"]]

        if not scenario_id or len(pairings) < 2:
            raise HTTPException(400, "Need scenario_id and 2+ model pairings")

        from dojo_scenarios import get_scenario
        scenario = get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(404, "Scenario not found")

        battle_id = f"dojo_battle_{uuid.uuid4().hex[:12]}"
        session_ids = []

        for pairing in pairings[:4]:
            # Create a Dojo session per pairing
            from dojo_engine import DojoEngine
            agents = []
            for i, role_def in enumerate(scenario["roles"]):
                model = pairing[i] if i < len(pairing) else pairing[0]
                agents.append({**role_def, "agent_id": f"dojo_{model}", "base_model": model})

            session_id = f"dojo_ses_{uuid.uuid4().hex[:12]}"
            session = {
                "session_id": session_id, "workspace_id": ws_id,
                "scenario_id": scenario_id, "status": "draft",
                "agents": agents, "task": scenario["default_task"],
                "config": scenario["config_defaults"],
                "turns": [], "turn_count": 0,
                "termination": None, "synthetic_data": None,
                "cost_tracking": {"total_cost_usd": 0, "per_agent": {}},
                "created_by": user["user_id"],
                "battle_id": battle_id,
                "created_at": now_iso(), "updated_at": now_iso(),
            }
            await db.dojo_sessions.insert_one(session)
            session_ids.append(session_id)

        # Store battle metadata
        await db.arena_battles.insert_one({
            "battle_id": battle_id, "workspace_id": ws_id,
            "type": "dojo_roleplay", "scenario_id": scenario_id,
            "pairings": pairings, "session_ids": session_ids,
            "status": "created", "created_by": user["user_id"],
            "created_at": now_iso(),
        })

        return {"battle_id": battle_id, "session_ids": session_ids}
'''


# ================================================================
# PATCH 8: frontend/src/components/NavigationSidebar.jsx
# Add menu item (React JSX)
# ================================================================

NAV_SIDEBAR_PATCH = '''
{/* Agent Dojo — add after Agent Studio or Arena menu item */}
<NavItem
  icon={<Dumbbell size={18} />}
  label="Agent Dojo"
  to={`/workspaces/${workspaceId}/dojo`}
  active={location.pathname.includes('/dojo')}
/>
'''
