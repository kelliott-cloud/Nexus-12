"""Dojo Engine — Core role-play loop with inception prompting.

Implements CAMEL-style autonomous agent-to-agent conversations with
Nexus-native integration: cost tracking, confidence scoring, tool calls,
semantic stall detection, and synthetic data extraction.

Reference: CAMEL (Li et al., 2023) — arxiv.org/abs/2303.17760
"""
import uuid
import asyncio
import time
import logging
from datetime import datetime, timezone

from nexus_utils import now_iso
from confidence_scoring import estimate_confidence

logger = logging.getLogger("dojo_engine")


class DojoEngine:
    """Orchestrates a role-playing session between two or more Nexus agents."""

    def __init__(self, db, ws_manager=None):
        self.db = db
        self.ws_manager = ws_manager

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    async def run_session(self, session_id: str):
        """Main execution loop — runs until termination condition is met."""
        session = await self.db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not session:
            return

        await self.db.dojo_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "running", "started_at": now_iso()}},
        )
        await self._emit(session_id, "dojo:session_started", {"session_id": session_id})

        config = session.get("config") or {}
        max_turns = config.get("max_turns", 50)
        cost_cap = config.get("cost_cap_usd", 2.0)
        turn_timeout = config.get("turn_timeout_sec", 120)
        agents = session.get("agents") or []
        task = session.get("task") or {}
        workspace_id = session.get("workspace_id", "")

        start_time = time.time()
        turn_number = session.get("turn_count", 0)
        total_cost = session.get("cost_tracking", {}).get("total_cost_usd", 0)

        # Build inception prompts for each agent
        from dojo_prompts import build_inception_prompt
        agent_prompts = {}
        for agent_def in agents:
            agent_prompts[agent_def["agent_id"]] = await build_inception_prompt(
                self.db, agent_def, agents, task, workspace_id
            )

        # ── Main Turn Loop ──────────────────────────────
        while turn_number < max_turns:
            # Refresh session status (might have been paused/cancelled externally)
            session = await self.db.dojo_sessions.find_one(
                {"session_id": session_id}, {"_id": 0}
            )
            if not session or session.get("status") in ("cancelled", "failed", "paused"):
                break

            # Cost guard
            if total_cost > cost_cap:
                await self._complete_session(
                    session_id, "cost_cap_exceeded",
                    f"Cost ${total_cost:.4f} exceeded cap ${cost_cap}"
                )
                break

            # Duration guard
            elapsed = time.time() - start_time
            session_timeout = config.get("session_timeout_sec", 600)
            if elapsed > session_timeout:
                await self._complete_session(
                    session_id, "timeout", f"Session exceeded {session_timeout}s"
                )
                break

            # Determine which agent speaks this turn (round-robin)
            agent_idx = turn_number % len(agents)
            current_agent = agents[agent_idx]
            agent_id = current_agent["agent_id"]

            await self._emit(session_id, "dojo:turn_started", {
                "session_id": session_id,
                "turn_number": turn_number,
                "agent_id": agent_id,
                "role": current_agent.get("role", ""),
            })

            # Execute the turn
            turn_result = await self._execute_turn(
                session_id, turn_number, current_agent,
                agent_prompts[agent_id], task, workspace_id, turn_timeout,
            )

            if turn_result.get("error"):
                logger.warning(f"Dojo turn {turn_number} failed: {turn_result['error']}")
                await self._complete_session(session_id, "turn_error", turn_result["error"])
                break

            total_cost += turn_result.get("cost_usd", 0)

            # Persist turn
            await self.db.dojo_sessions.update_one(
                {"session_id": session_id},
                {
                    "$push": {"turns": turn_result},
                    "$set": {
                        "turn_count": turn_number + 1,
                        "cost_tracking.total_cost_usd": total_cost,
                        "updated_at": now_iso(),
                    },
                    "$inc": {
                        f"cost_tracking.per_agent.{agent_id}": turn_result.get("cost_usd", 0),
                    },
                },
            )

            await self._emit(session_id, "dojo:turn_completed", {
                "session_id": session_id,
                "turn_number": turn_number,
                "agent_id": agent_id,
                "content_preview": turn_result.get("content", "")[:200],
                "confidence": turn_result.get("confidence", {}),
            })

            # ── Termination Checks ──────────────────────
            content = turn_result.get("content", "")

            # 1. Explicit task_complete marker (Nexus convention)
            if "[STATUS: task_complete]" in content:
                await self._complete_session(
                    session_id, "task_complete", "Agent signaled task completion"
                )
                break

            # 2. CAMEL-style TASK_DONE marker (compatibility)
            if "<TASK_DONE>" in content or "TASK_DONE" in content:
                await self._complete_session(
                    session_id, "task_complete", "CAMEL TASK_DONE marker detected"
                )
                break

            # 3. Stall detection via semantic similarity (3+ repetitive turns)
            if turn_number >= 4:
                is_stalled = await self._detect_stall(session_id, turn_number)
                if is_stalled:
                    anti_stall_count = session.get("_anti_stall_count", 0)
                    if anti_stall_count >= 2:
                        await self._complete_session(
                            session_id, "stall_detected",
                            "Conversation stalled after anti-stall attempts"
                        )
                        break
                    else:
                        await self.db.dojo_sessions.update_one(
                            {"session_id": session_id},
                            {"$inc": {"_anti_stall_count": 1}},
                        )

            turn_number += 1

        # ── Session Finalization ────────────────────────
        session = await self.db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if session and session.get("status") == "running":
            await self._complete_session(
                session_id, "turn_limit_reached", f"Reached max turns: {max_turns}"
            )

    # ----------------------------------------------------------------
    # Turn Execution
    # ----------------------------------------------------------------

    async def _execute_turn(self, session_id, turn_number, agent_def,
                            system_prompt, task, workspace_id, timeout):
        """Execute a single agent turn in the role-play session."""
        agent_id = agent_def["agent_id"]
        base_model = agent_def.get("base_model", "claude")

        # Phase-aware model selection for cost optimization
        try:
            from smart_routing import get_dojo_optimal_model
            session_config = (await self.db.dojo_sessions.find_one(
                {"session_id": session_id}, {"_id": 0, "config": 1}
            ) or {}).get("config", {})
            max_turns = session_config.get("max_turns", 50)
            from collaboration_core import get_ai_key_for_agent
            available = []
            for model_key in ["groq", "deepseek", "chatgpt", "gemini", "claude"]:
                key, _ = await get_ai_key_for_agent("", workspace_id, model_key)
                if key:
                    available.append(model_key)
            if available:
                base_model = get_dojo_optimal_model(turn_number, max_turns, available)
        except Exception as e:
            logger.debug(f"Phase routing fallback to {base_model}: {e}")

        # Build conversation context from previous turns
        session = await self.db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "turns": 1, "task": 1}
        )
        turns = session.get("turns") or []

        context = f"Task: {task.get('description', '')}\n"
        context += f"Success criteria: {task.get('success_criteria', '')}\n\n"
        context += "Conversation so far:\n"
        for t in turns[-20:]:  # Last 20 turns for context window management
            role = t.get("role", "Agent")
            content = t.get("content", "")
            if len(content) > 2000:
                content = content[:2000] + "... [truncated]"
            context += f"[{role}]: {content}\n\n"
        context += "It is now your turn. Respond as your role."

        # Get API key via existing Nexus key resolution chain
        from collaboration_core import get_ai_key_for_agent
        user_id = (await self.db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "created_by": 1}
        ) or {}).get("created_by", "")
        api_key, key_source = await get_ai_key_for_agent(
            user_id, workspace_id, base_model
        )

        if not api_key:
            return {"error": f"No API key for {base_model}", "turn_number": turn_number}

        # Call AI via existing provider infrastructure
        from ai_providers import call_ai_direct
        start = time.time()
        try:
            response = await asyncio.wait_for(
                call_ai_direct(
                    base_model, api_key, system_prompt, context,
                    workspace_id=workspace_id, db=self.db,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {"error": f"Turn timed out after {timeout}s", "turn_number": turn_number}
        except Exception as e:
            return {"error": str(e)[:300], "turn_number": turn_number}
        duration_ms = int((time.time() - start) * 1000)

        # Confidence scoring (reuse existing module)
        confidence = estimate_confidence(response)

        # Estimate cost via smart_routing
        from smart_routing import estimate_cost
        est_tokens_in = len(context) // 4
        est_tokens_out = len(response) // 4
        cost = estimate_cost(base_model, est_tokens_in, est_tokens_out)

        # Parse tool calls if present
        tool_calls = []
        try:
            from routes.routes_ai_tools import parse_tool_calls
            tool_calls = parse_tool_calls(response) or []
        except Exception as _e:
            import logging; logging.getLogger("dojo_engine").warning(f"Suppressed: {_e}")

        return {
            "turn_number": turn_number,
            "agent_id": agent_id,
            "role": agent_def.get("role", ""),
            "base_model": base_model,
            "content": response,
            "confidence": confidence,
            "tool_calls": [tc.get("tool", "") for tc in tool_calls],
            "tokens_in": est_tokens_in,
            "tokens_out": est_tokens_out,
            "cost_usd": cost,
            "duration_ms": duration_ms,
            "timestamp": now_iso(),
        }

    # ----------------------------------------------------------------
    # Stall Detection (semantic similarity via existing module)
    # ----------------------------------------------------------------

    async def _detect_stall(self, session_id, current_turn):
        """Detect repetitive turns using TF-IDF cosine similarity."""
        from semantic_memory import _tokenize
        from collections import Counter
        from math import sqrt

        session = await self.db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "turns": 1}
        )
        turns = session.get("turns") or []
        if len(turns) < 4:
            return False

        recent = [t.get("content", "") for t in turns[-4:]]
        vectors = []
        for text in recent:
            tokens = _tokenize(text)
            vectors.append(Counter(tokens))

        # Check pairwise similarity of last 3 consecutive turns
        similarities = []
        for i in range(len(vectors) - 1):
            keys = set(vectors[i].keys()) & set(vectors[i + 1].keys())
            if not keys:
                similarities.append(0.0)
                continue
            dot = sum(vectors[i][k] * vectors[i + 1][k] for k in keys)
            m1 = sqrt(sum(v**2 for v in vectors[i].values()))
            m2 = sqrt(sum(v**2 for v in vectors[i + 1].values()))
            sim = dot / (m1 * m2) if m1 and m2 else 0
            similarities.append(sim)

        return all(s > 0.85 for s in similarities)

    # ----------------------------------------------------------------
    # Session Lifecycle
    # ----------------------------------------------------------------

    async def _complete_session(self, session_id, reason, summary=""):
        """Finalize a session and trigger data extraction."""
        await self.db.dojo_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "completed_at": now_iso(),
                "termination": {
                    "reason": reason,
                    "detected_at": now_iso(),
                    "final_summary": summary,
                },
            }},
        )
        await self._emit(session_id, "dojo:session_completed", {
            "session_id": session_id, "reason": reason,
        })

        # Auto-extract synthetic data in background
        try:
            from dojo_data_extractor import extract_training_data
            await extract_training_data(self.db, session_id)
        except Exception as e:
            logger.warning(f"Auto-extract failed: {e}")

    async def _emit(self, session_id, event, data):
        """Emit WebSocket event through existing Nexus infrastructure."""
        if self.ws_manager:
            try:
                session = await self.db.dojo_sessions.find_one(
                    {"session_id": session_id}, {"_id": 0, "workspace_id": 1}
                )
                ws_id = session.get("workspace_id", "") if session else ""
                await self.ws_manager.broadcast(ws_id, {"type": event, **data})
            except Exception as _e:
                import logging; logging.getLogger("dojo_engine").warning(f"Suppressed: {_e}")
