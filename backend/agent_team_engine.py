"""Agent Team Engine — Autonomous multi-model task execution with self-correction."""
import asyncio
import logging
from nexus_utils import now_iso, gen_id

logger = logging.getLogger(__name__)

TASK_TYPE_MODEL_MAP = {
    "research": ["perplexity", "gemini", "chatgpt"],
    "data_analysis": ["chatgpt", "claude", "deepseek"],
    "code_writing": ["claude", "deepseek", "chatgpt"],
    "creative_writing": ["claude", "chatgpt", "gemini"],
    "review": ["claude", "gemini", "chatgpt"],
    "summarization": ["gemini", "chatgpt", "groq"],
    "reasoning": ["claude", "chatgpt", "deepseek"],
}

DECOMPOSITION_SYSTEM = "You are a task decomposition engine. Break complex goals into concrete, independent subtasks. Each subtask must be completable by a single AI model in one turn. Return ONLY valid JSON."
DECOMPOSITION_USER = """Decompose this goal into subtasks.
Goal: {goal}
Return JSON: {{"subtasks": [{{"title": "...", "description": "specific instructions", "task_type": "research|data_analysis|code_writing|creative_writing|review|summarization|reasoning", "estimated_complexity": "light|standard|premium"}}], "dependency_graph": {{"sub_0": [], "sub_1": ["sub_0"]}}}}"""


class AgentTeamEngine:
    def __init__(self, db, ws_manager=None):
        self.db = db
        self.ws_manager = ws_manager

    async def _broadcast(self, session_id, event_type, payload):
        """Broadcast agent team events via WebSocket for real-time UI."""
        session = await self.db.agent_team_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "channel_id": 1})
        channel_id = (session or {}).get("channel_id", "")
        if channel_id and self.ws_manager:
            try:
                await self.ws_manager.broadcast(channel_id, {
                    "type": "agent_team_update", "session_id": session_id,
                    "event": event_type, "payload": payload,
                })
            except Exception:
                pass

    async def start_session(self, goal, workspace_id, channel_id, user_id, settings=None):
        session_id = gen_id("ats")
        session = {
            "session_id": session_id, "workspace_id": workspace_id,
            "channel_id": channel_id, "goal": goal,
            "status": "decomposing", "initiated_by": user_id,
            "decomposition": None, "subtasks": [],
            "final_output": None, "overall_confidence": None,
            "total_cost_usd": 0, "escalation": None,
            "audit_trail": [{"event": "created", "timestamp": now_iso(), "detail": goal[:200]}],
            "settings": settings or {"max_cost_usd": 1.0, "max_retries_per_subtask": 2,
                                     "confidence_threshold": 0.7, "auto_approve": False},
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await self.db.agent_team_sessions.insert_one(session)
        asyncio.create_task(self._execute(session_id))
        return session_id

    async def _execute(self, session_id):
        try:
            subtasks = await self._decompose(session_id)
            if not subtasks:
                await self._fail(session_id, "Decomposition produced no subtasks")
                return
            await self._assign_models(session_id)
            await self._execute_subtasks(session_id)
            await self._cross_validate(session_id)

            session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
            overall = self._compute_overall_confidence(session.get("subtasks", []))
            threshold = session.get("settings", {}).get("confidence_threshold", 0.7)
            if overall < threshold:
                await self._escalate_to_human(session_id, overall, threshold)
                return
            await self._assemble_and_deliver(session_id)
        except Exception as e:
            logger.error(f"Agent team {session_id} failed: {e}")
            await self._fail(session_id, str(e))

    async def _decompose(self, session_id):
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        goal = session["goal"]
        ws_id = session["workspace_id"]
        from collaboration_core import get_ai_key_for_agent
        from ai_providers import call_ai_direct
        for agent in ["claude", "chatgpt", "gemini"]:
            api_key, _ = await get_ai_key_for_agent("system", ws_id, agent)
            if api_key:
                try:
                    result = await call_ai_direct(agent, api_key, DECOMPOSITION_SYSTEM,
                        DECOMPOSITION_USER.format(goal=goal), workspace_id=ws_id, db=self.db)
                    from workflow_engine import parse_ai_json
                    parsed = parse_ai_json(result)
                    subtasks = parsed.get("subtasks", [])
                    deps = parsed.get("dependency_graph", {})
                    subtask_docs = [{"subtask_id": f"sub_{i}", **st, "status": "pending",
                        "assigned_model": None, "assignment_reason": "",
                        "output": None, "confidence": None, "validation": None,
                        "retries": 0, "cost_usd": 0} for i, st in enumerate(subtasks)]
                    await self.db.agent_team_sessions.update_one(
                        {"session_id": session_id},
                        {"$set": {"decomposition": {"model_used": agent, "subtask_count": len(subtasks),
                                    "dependency_graph": deps, "created_at": now_iso()},
                                  "subtasks": subtask_docs, "status": "running", "updated_at": now_iso()},
                         "$push": {"audit_trail": {"event": "decomposed", "timestamp": now_iso(),
                                    "detail": f"Split into {len(subtasks)} subtasks by {agent}"}}})
                    await self._broadcast(session_id, "decomposed", {"subtask_count": len(subtasks)})
                    return subtasks
                except Exception as e:
                    logger.warning(f"Decomposition failed with {agent}: {e}")
        return []

    async def _assign_models(self, session_id):
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        ws_id = session["workspace_id"]
        from collaboration_core import get_ai_key_for_agent
        for st in session.get("subtasks", []):
            task_type = st.get("task_type", "reasoning")
            candidates = TASK_TYPE_MODEL_MAP.get(task_type, ["chatgpt", "claude"])
            for model in candidates:
                api_key, _ = await get_ai_key_for_agent("system", ws_id, model)
                if api_key:
                    await self.db.agent_team_sessions.update_one(
                        {"session_id": session_id, "subtasks.subtask_id": st["subtask_id"]},
                        {"$set": {"subtasks.$.assigned_model": model,
                                  "subtasks.$.assignment_reason": f"Best available for {task_type}"}})
                    break

    async def _execute_subtasks(self, session_id):
        """Execute subtasks respecting dependency graph — parallel where possible."""
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        ws_id = session["workspace_id"]
        deps = (session.get("decomposition") or {}).get("dependency_graph", {})
        subtasks = session.get("subtasks", [])
        from collaboration_core import get_ai_key_for_agent
        from ai_providers import call_ai_direct

        completed = set()
        max_iterations = len(subtasks) * 3
        iteration = 0

        while len(completed) < len(subtasks) and iteration < max_iterations:
            iteration += 1
            # Find all runnable subtasks (deps satisfied, not yet completed)
            runnable = []
            for st in subtasks:
                sid = st["subtask_id"]
                if sid in completed:
                    continue
                dep_list = deps.get(sid, [])
                if all(d in completed for d in dep_list):
                    runnable.append(st)

            if not runnable:
                break  # Deadlock or all done

            # Execute runnable tasks in parallel
            async def _run_one(st):
                sid = st["subtask_id"]
                model = st.get("assigned_model", "chatgpt")
                api_key, _ = await get_ai_key_for_agent("system", ws_id, model)
                if not api_key:
                    st["status"] = "failed"
                    st["output"] = f"No API key for {model}"
                    return sid
                try:
                    dep_context = ""
                    for d in deps.get(sid, []):
                        dep_st = next((s for s in subtasks if s["subtask_id"] == d), None)
                        if dep_st and dep_st.get("output"):
                            dep_context += f"\n[Output from {d}]: {dep_st['output'][:500]}\n"
                    # KG context injection
                    kg_context = ""
                    try:
                        from knowledge_graph import KnowledgeGraphEngine, ConsentChecker
                        if await ConsentChecker.is_workspace_kg_enabled(self.db, ws_id):
                            kg = KnowledgeGraphEngine(self.db)
                            kg_context = await kg.retrieve_context(st.get("description", ""), ws_id, max_entities=5, max_tokens=1000)
                    except Exception:
                        pass
                    prompt = f"Task: {st.get('title','')}\n{st.get('description','')}{dep_context}{kg_context}"
                    output = await call_ai_direct(model, api_key,
                        "You are completing a subtask as part of a larger goal. Be thorough and precise.",
                        prompt, workspace_id=ws_id, db=self.db)
                    st["output"] = output
                    st["status"] = "completed"
                    st["confidence"] = 0.8
                    try:
                        from smart_routing import estimate_cost
                        input_tokens = int(len(prompt.split()) * 1.3)
                        output_tokens = int(len(output.split()) * 1.3)
                        cost = estimate_cost(model, input_tokens, output_tokens)
                        st["cost_usd"] = cost
                        await self.db.agent_team_sessions.update_one(
                            {"session_id": session_id}, {"$inc": {"total_cost_usd": cost}})
                        session_now = await self.db.agent_team_sessions.find_one(
                            {"session_id": session_id}, {"_id": 0, "total_cost_usd": 1, "settings": 1})
                        max_cost = (session_now or {}).get("settings", {}).get("max_cost_usd", 1.0)
                        if (session_now or {}).get("total_cost_usd", 0) > max_cost:
                            raise Exception(f"Cost budget exceeded: ${session_now['total_cost_usd']:.4f} > ${max_cost}")
                    except Exception as ce:
                        if "Cost budget exceeded" in str(ce):
                            raise
                    await self.db.agent_team_sessions.update_one(
                        {"session_id": session_id, "subtasks.subtask_id": sid},
                        {"$set": {"subtasks.$.output": output, "subtasks.$.status": "completed",
                                  "subtasks.$.confidence": 0.8, "subtasks.$.cost_usd": st.get("cost_usd", 0)}})
                    await self._audit(session_id, "subtask_completed", f"{sid} by {model}")
                    await self._broadcast(session_id, "subtask_completed", {"subtask_id": sid, "model": model})
                except Exception as e:
                    logger.warning(f"Subtask {sid} failed: {e}")
                    st["status"] = "failed"
                    st["retries"] = st.get("retries", 0) + 1
                    await self.db.agent_team_sessions.update_one(
                        {"session_id": session_id, "subtasks.subtask_id": sid},
                        {"$set": {"subtasks.$.status": "failed", "subtasks.$.retries": st["retries"]}})
                    max_retries = session.get("settings", {}).get("max_retries_per_subtask", 2)
                    if st["retries"] > max_retries:
                        return sid
                    return None
                return sid

            results = await asyncio.gather(*[_run_one(st) for st in runnable], return_exceptions=True)
            for r in results:
                if isinstance(r, str):
                    completed.add(r)

    async def _cross_validate(self, session_id):
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        ws_id = session["workspace_id"]
        from collaboration_core import get_ai_key_for_agent
        from ai_providers import call_ai_direct
        for st in session.get("subtasks", []):
            if st.get("status") != "completed" or not st.get("output"):
                continue
            validator = "gemini" if st.get("assigned_model") != "gemini" else "claude"
            api_key, _ = await get_ai_key_for_agent("system", ws_id, validator)
            if not api_key:
                continue
            try:
                result = await call_ai_direct(validator, api_key,
                    "You are a quality reviewer. Rate the output 0-100 and list issues. Return JSON: {\"score\": N, \"issues\": []}",
                    f"Task: {st.get('title','')}\nOutput to review:\n{st['output'][:3000]}",
                    workspace_id=ws_id, db=self.db)
                from workflow_engine import parse_ai_json
                parsed = parse_ai_json(result)
                score = parsed.get("score", 70) / 100
                await self.db.agent_team_sessions.update_one(
                    {"session_id": session_id, "subtasks.subtask_id": st["subtask_id"]},
                    {"$set": {"subtasks.$.validation": {"validator_model": validator,
                              "score": score, "issues": parsed.get("issues", []),
                              "validated_at": now_iso()},
                              "subtasks.$.confidence": score}})
                await self._audit(session_id, "validation", f"{st['subtask_id']} score: {score:.2f}")
                await self._broadcast(session_id, "validated", {"subtask_id": st["subtask_id"], "score": score})
                # Auto-retry low-scoring subtasks
                min_score = session.get("settings", {}).get("min_subtask_score", 0.6)
                max_retries = session.get("settings", {}).get("max_retries_per_subtask", 2)
                if score < min_score and st.get("retries", 0) < max_retries:
                    feedback = f"Previous attempt scored {score:.0%}. Issues: {parsed.get('issues', [])}"
                    await self.db.agent_team_sessions.update_one(
                        {"session_id": session_id, "subtasks.subtask_id": st["subtask_id"]},
                        {"$set": {"subtasks.$.status": "pending", "subtasks.$.output": None,
                                  "subtasks.$.description": st.get("description", "") + f"\n\nReviewer feedback: {feedback}"},
                         "$inc": {"subtasks.$.retries": 1}})
                    await self._audit(session_id, "subtask_retry", f"{st['subtask_id']} score {score:.2f} < {min_score}")
            except Exception as e:
                logger.debug(f"Validation failed for {st['subtask_id']}: {e}")

    def _compute_overall_confidence(self, subtasks):
        scores = [s.get("confidence", 0) for s in subtasks if s.get("confidence")]
        return sum(scores) / max(len(scores), 1)

    async def _escalate_to_human(self, session_id, confidence, threshold):
        await self.db.agent_team_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "escalated", "overall_confidence": confidence,
                      "escalation": {"reason": f"Confidence {confidence:.0%} below {threshold:.0%}",
                                     "escalated_at": now_iso()},
                      "updated_at": now_iso()},
             "$push": {"audit_trail": {"event": "escalated", "timestamp": now_iso(),
                        "detail": f"Confidence {confidence:.2f} < {threshold:.2f}"}}})
        await self._broadcast(session_id, "escalated", {"confidence": confidence, "threshold": threshold})
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if session and session.get("channel_id"):
            await self.db.messages.insert_one({
                "message_id": gen_id("msg"), "channel_id": session["channel_id"],
                "sender_type": "system", "sender_id": "agent_team", "sender_name": "Agent Team",
                "content": f"I need your review. Confidence: {confidence:.0%} (threshold: {threshold:.0%}). "
                           f"Please review subtask outputs and approve or provide feedback.",
                "metadata": {"agent_team_session_id": session_id, "action_required": "review"},
                "created_at": now_iso(),
            })

    async def _assemble_and_deliver(self, session_id):
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        outputs = []
        for st in session.get("subtasks", []):
            if st.get("output"):
                outputs.append(f"## {st.get('title','')}\n{st['output']}")
        final = "\n\n---\n\n".join(outputs)
        overall = self._compute_overall_confidence(session.get("subtasks", []))
        total_cost = sum(st.get("cost_usd", 0) for st in session.get("subtasks", []))
        await self.db.agent_team_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "completed", "final_output": final,
                      "overall_confidence": overall, "total_cost_usd": total_cost, "updated_at": now_iso()},
             "$push": {"audit_trail": {"event": "completed", "timestamp": now_iso(),
                        "detail": f"Assembled {len(outputs)} outputs"}}})
        if session.get("channel_id"):
            await self.db.messages.insert_one({
                "message_id": gen_id("msg"), "channel_id": session["channel_id"],
                "sender_type": "system", "sender_id": "agent_team", "sender_name": "Agent Team",
                "content": f"Task complete (confidence: {overall:.0%}).\n\n{final[:4000]}",
                "metadata": {"agent_team_session_id": session_id}, "created_at": now_iso(),
            })
        await self._broadcast(session_id, "completed", {"overall_confidence": overall})
        # Feed completed session into Knowledge Graph
        try:
            from knowledge_graph import ConsentChecker
            from knowledge_graph_hooks import on_message_created
            if await ConsentChecker.is_workspace_kg_enabled(self.db, session["workspace_id"]):
                import asyncio as _aio
                fake_msg = {
                    "content": f"Agent team completed: {session['goal']}\n\nKey outputs: {final[:2000]}",
                    "channel_id": session.get("channel_id", ""),
                    "message_id": session_id,
                    "sender_id": "agent_team", "sender_type": "system"}
                _aio.create_task(on_message_created(self.db, fake_msg, {}, session["workspace_id"]))
        except Exception:
            pass

    async def _fail(self, session_id, error):
        await self.db.agent_team_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "failed", "error": error[:500], "updated_at": now_iso()},
             "$push": {"audit_trail": {"event": "failed", "timestamp": now_iso(), "detail": error[:200]}}})

    async def _audit(self, session_id, event, detail):
        await self.db.agent_team_sessions.update_one(
            {"session_id": session_id},
            {"$push": {"audit_trail": {"event": event, "timestamp": now_iso(), "detail": detail[:200]}}})

    async def _retry_with_feedback(self, session_id, feedback):
        session = await self.db.agent_team_sessions.find_one({"session_id": session_id}, {"_id": 0})
        threshold = session.get("settings", {}).get("confidence_threshold", 0.7)
        for st in session.get("subtasks", []):
            if (st.get("confidence") or 0) < threshold or st.get("status") == "failed":
                await self.db.agent_team_sessions.update_one(
                    {"session_id": session_id, "subtasks.subtask_id": st["subtask_id"]},
                    {"$set": {"subtasks.$.status": "pending", "subtasks.$.output": None,
                              "subtasks.$.confidence": None, "subtasks.$.validation": None,
                              "subtasks.$.description": st.get("description", "") + f"\n\nHuman feedback: {feedback[:500]}"}})
        await self.db.agent_team_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "running", "escalation.resolved_at": now_iso()},
             "$push": {"audit_trail": {"event": "retry_with_feedback", "timestamp": now_iso(), "detail": feedback[:200]}}})
        asyncio.create_task(self._execute(session_id))
