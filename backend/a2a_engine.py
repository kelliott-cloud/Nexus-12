from nexus_utils import now_iso
"""A2A Engine — Agent-to-Agent Autonomous Workflow Execution Engine.
Executes multi-agent pipelines with quality gates, routing, retries, and cost tracking."""
import uuid
import asyncio
import json
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)



class A2AEngine:
    def __init__(self, db, ws_manager=None):
        self.db = db
        self.ws_manager = ws_manager

    async def execute_pipeline(self, run_id: str):
        """Main execution loop for an A2A pipeline run."""
        run = await self.db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            return
        pipeline = await self.db.a2a_pipelines.find_one({"pipeline_id": run["pipeline_id"]}, {"_id": 0})
        if not pipeline:
            await self._fail_run(run_id, "Pipeline not found")
            return

        await self._emit(run_id, "pipeline:started", {"pipeline_id": pipeline["pipeline_id"], "name": pipeline["name"]})

        steps = pipeline.get("steps") or []
        settings = pipeline.get("settings") or {}
        max_cost = settings.get("max_total_cost_usd", 5.0)
        max_duration = settings.get("max_total_duration_sec", 600)
        on_failure = settings.get("on_failure", "pause_and_notify")
        start_time = time.time()

        # Determine starting step
        current_step_id = run.get("current_step_id")
        if not current_step_id and steps:
            current_step_id = steps[0].get("step_id", "step_0")

        while current_step_id:
            # Cost guard
            run = await self.db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
            if not run or run.get("status") in ("cancelled", "failed"):
                break
            if run.get("total_cost_usd", 0) > max_cost:
                await self._fail_run(run_id, f"Cost limit exceeded: ${run['total_cost_usd']:.4f} > ${max_cost}")
                await self._notify_channel(pipeline, run_id, f"Pipeline **{pipeline['name']}** aborted: cost limit ${max_cost} exceeded.")
                break
            if (time.time() - start_time) > max_duration:
                await self._fail_run(run_id, f"Duration limit exceeded: {max_duration}s")
                break

            # Find step definition
            step = None
            for s in steps:
                if s.get("step_id") == current_step_id:
                    step = s
                    break
            if not step:
                await self._fail_run(run_id, f"Step {current_step_id} not found in pipeline")
                break

            # Update current step
            await self.db.a2a_runs.update_one({"run_id": run_id}, {"$set": {"current_step_id": current_step_id}})

            # Execute step
            result = await self._execute_step(run_id, run, pipeline, step)

            if result["status"] == "failed":
                if on_failure == "abort_pipeline":
                    await self._fail_run(run_id, f"Step {current_step_id} failed: {result.get('error', '')}")
                    await self._notify_channel(pipeline, run_id, f"Pipeline **{pipeline['name']}** failed at step **{step.get('name', current_step_id)}**.")
                    break
                elif on_failure == "skip_step":
                    pass  # Continue to next step
                else:  # pause_and_notify
                    await self.db.a2a_runs.update_one({"run_id": run_id}, {"$set": {"status": "paused", "pause_reason": f"Step {current_step_id} failed: {result.get('error', '')}"}})
                    await self._emit(run_id, "pipeline:paused", {"step_id": current_step_id, "reason": result.get("error", "")})
                    await self._notify_channel(pipeline, run_id, f"Pipeline **{pipeline['name']}** paused at step **{step.get('name', current_step_id)}**. Resume from the A2A panel.")
                    break
            elif result["status"] == "human_gate":
                await self.db.a2a_runs.update_one({"run_id": run_id}, {"$set": {"status": "paused", "pause_reason": f"Human approval required at step {current_step_id}"}})
                await self._emit(run_id, "pipeline:paused", {"step_id": current_step_id, "reason": "human_gate"})
                await self._notify_channel(pipeline, run_id, f"Pipeline **{pipeline['name']}** needs human approval at step **{step.get('name', current_step_id)}**.")
                break

            # Resolve routing to next step
            current_step_id = await self._resolve_routing(step, result, run_id)

        # Check if completed (not paused/failed/cancelled)
        run = await self.db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
        if run and run.get("status") == "running":
            total_dur = int((time.time() - start_time) * 1000)
            await self.db.a2a_runs.update_one({"run_id": run_id}, {"$set": {
                "status": "completed", "completed_at": now_iso(), "current_step_id": None,
                "total_duration_ms": total_dur,
            }})
            await self._emit(run_id, "pipeline:completed", {"run_id": run_id, "duration_ms": total_dur})
            await self._notify_channel(pipeline, run_id, f"Pipeline **{pipeline['name']}** completed successfully.")
            logger.info(f"A2A pipeline {pipeline['pipeline_id']} run {run_id} completed in {total_dur}ms")

    async def _execute_step(self, run_id, run, pipeline, step):
        """Execute a single pipeline step with retries and quality gates."""
        step_id = step.get("step_id", "")
        agent_id = step.get("agent_id", "")
        settings = pipeline.get("settings") or {}
        max_retries = min((step.get("quality_gate") or {}).get("max_retries", settings.get("max_retries_per_step", 3)), 5)  # Hard cap at 5

        # Human gate check
        routing = step.get("routing") or {}
        if routing.get("type") == "human_gate":
            return {"status": "human_gate", "output": ""}

        retry_feedback = ""
        for attempt in range(max_retries + 1):
            exec_id = f"a2a_exec_{uuid.uuid4().hex[:10]}"
            start = time.time()

            await self.db.a2a_step_executions.insert_one({
                "exec_id": exec_id, "run_id": run_id, "step_id": step_id,
                "agent_id": agent_id, "attempt": attempt + 1, "status": "running",
                "input_prompt": "", "output": "", "tools_used": [], "tool_results": [],
                "quality_score": None, "quality_feedback": None,
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0,
                "duration_ms": 0, "started_at": now_iso(), "completed_at": None, "error": None,
            })
            await self._emit(run_id, "step:started", {"step_id": step_id, "attempt": attempt + 1, "agent": agent_id})

            try:
                # Build prompt
                prompt = self._build_step_prompt(step, run, retry_feedback)

                # Resolve agent and API key
                agent_config = await self._resolve_agent(agent_id)
                model_key = agent_config.get("base_model", agent_id)
                api_key = await self._resolve_api_key(run.get("workspace_id", ""), model_key)

                if not api_key:
                    raise Exception(f"No API key available for model {model_key}")

                # Inject training knowledge if available
                system_prompt = step.get("system_prompt_override") or agent_config.get("system_prompt", "You are a helpful AI assistant.")
                try:
                    from agent_knowledge_retrieval import retrieve_training_knowledge
                    knowledge = await retrieve_training_knowledge(self.db, agent_id, prompt, max_chunks=5, max_tokens=2000)
                    if knowledge:
                        system_prompt += f"\n\n## Relevant Knowledge:\n{knowledge}"
                except Exception as _e:
                    import logging; logging.getLogger("a2a_engine").warning(f"Suppressed: {_e}")

                # Call AI
                from ai_providers import call_ai_direct
                output = await call_ai_direct(model_key, api_key, system_prompt, prompt)

                duration_ms = int((time.time() - start) * 1000)
                tokens_in = len(prompt.split()) * 1.3
                tokens_out = len(output.split()) * 1.3
                from workflow_engine import calc_cost
                cost = calc_cost(model_key, int(tokens_in), int(tokens_out))

                # Update execution
                await self.db.a2a_step_executions.update_one({"exec_id": exec_id}, {"$set": {
                    "status": "completed", "input_prompt": prompt[:2000], "output": output[:5000],
                    "tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
                    "cost_usd": cost, "duration_ms": duration_ms, "completed_at": now_iso(),
                }})

                # Update run totals
                await self.db.a2a_runs.update_one({"run_id": run_id}, {
                    "$inc": {"total_cost_usd": cost, "total_tokens_in": int(tokens_in), "total_tokens_out": int(tokens_out)},
                    "$set": {f"step_outputs.{step_id}": {"output": output[:3000], "quality_score": None, "cost_usd": cost, "duration_ms": duration_ms, "retries": attempt}},
                })

                # Quality gate
                gate = step.get("quality_gate") or {}
                if gate.get("enabled"):
                    score, feedback = await self._run_quality_gate(gate, output, step, run)
                    await self.db.a2a_step_executions.update_one({"exec_id": exec_id}, {"$set": {"quality_score": score, "quality_feedback": feedback}})
                    await self.db.a2a_runs.update_one({"run_id": run_id}, {"$set": {f"step_outputs.{step_id}.quality_score": score}})

                    min_score = gate.get("min_score", 0.7)
                    if score < min_score:
                        if attempt < max_retries:
                            retry_feedback = f"Previous attempt scored {score:.2f}. Feedback: {feedback}. Please improve."
                            await self._emit(run_id, "step:retry", {"step_id": step_id, "attempt": attempt + 1, "score": score, "feedback": feedback})
                            await self.db.a2a_step_executions.update_one({"exec_id": exec_id}, {"$set": {"status": "retrying"}})
                            continue
                        else:
                            return {"status": "failed", "error": f"Quality gate failed after {max_retries + 1} attempts. Last score: {score:.2f}", "output": output}

                await self._emit(run_id, "step:completed", {"step_id": step_id, "cost": cost, "duration_ms": duration_ms})
                return {"status": "completed", "output": output}

            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                error_msg = str(e)[:500]
                await self.db.a2a_step_executions.update_one({"exec_id": exec_id}, {"$set": {
                    "status": "failed", "error": error_msg, "duration_ms": duration_ms, "completed_at": now_iso(),
                }})
                if attempt < max_retries:
                    retry_feedback = f"Previous attempt failed: {error_msg}. Please try a different approach."
                    continue
                return {"status": "failed", "error": error_msg, "output": ""}

        return {"status": "failed", "error": "Max retries exhausted", "output": ""}

    async def _resolve_routing(self, step, step_result, run_id):
        """Determine next step based on routing rules."""
        routing = step.get("routing") or {}
        route_type = routing.get("type", "sequential")
        output = step_result.get("output", "")

        if route_type == "sequential":
            return routing.get("next_step_id")
        elif route_type == "conditional":
            for cond in routing.get("conditions") or []:
                rule = cond.get("if", "")
                if rule.startswith("output_contains:"):
                    keyword = rule.split(":", 1)[1]
                    if keyword.lower() in output.lower():
                        return cond.get("then")
                elif rule.startswith("output_length>"):
                    threshold = int(rule.split(">", 1)[1])
                    if len(output) > threshold:
                        return cond.get("then")
            return routing.get("default") or routing.get("next_step_id")
        elif route_type == "parallel":
            # Execute all parallel steps concurrently
            next_ids = routing.get("next_step_ids") or []
            if next_ids:
                run = await self.db.a2a_runs.find_one({"run_id": run_id}, {"_id": 0})
                pipeline = await self.db.a2a_pipelines.find_one({"pipeline_id": run["pipeline_id"]}, {"_id": 0})
                tasks = []
                for nid in next_ids:
                    for s in pipeline.get("steps") or []:
                        if s.get("step_id") == nid:
                            tasks.append(self._execute_step(run_id, run, pipeline, s))
                            break
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            return routing.get("merge_to")
        return None

    async def _run_quality_gate(self, gate, output, step, run):
        """Run quality validation on step output."""
        method = gate.get("method", "keyword_check")

        if method == "keyword_check":
            keywords = gate.get("required_keywords") or []
            if not keywords:
                return (1.0, "No keywords to check")
            found = sum(1 for k in keywords if k.lower() in output.lower())
            score = found / len(keywords)
            return (score, f"Found {found}/{len(keywords)} keywords")

        elif method == "regex":
            pattern = gate.get("pattern", "")
            if pattern and re.search(pattern, output, re.IGNORECASE):
                return (1.0, "Pattern matched")
            return (0.0, "Pattern not matched")

        elif method == "json_schema":
            try:
                parsed = json.loads(output)
                required = gate.get("required_fields") or []
                found = sum(1 for f in required if f in parsed)
                score = found / max(len(required), 1)
                return (score, f"Found {found}/{len(required)} required fields")
            except json.JSONDecodeError:
                return (0.0, "Output is not valid JSON")

        elif method == "ai_validation":
            try:
                validator = gate.get("validator_agent_id", "claude")
                prompt = gate.get("validation_prompt", "Score this output 0.0-1.0. Respond with JSON: {\"score\": 0.0, \"feedback\": \"...\"}")
                prompt = prompt.replace("{output}", output[:3000])
                api_key = await self._resolve_api_key(run.get("workspace_id", ""), validator)
                from ai_providers import call_ai_direct
                result = await call_ai_direct(validator, api_key, "You are a quality validator. Always respond with JSON: {\"score\": 0.0, \"feedback\": \"...\"}", prompt)
                try:
                    from workflow_engine import parse_ai_json
                    parsed = parse_ai_json(result)
                    return (float(parsed.get("score", 0.5)), parsed.get("feedback", ""))
                except Exception:
                    return (0.5, result[:200])
            except Exception as e:
                return (0.5, f"Validation error: {str(e)[:100]}")

        return (0.5, "Unknown validation method")

    def _build_step_prompt(self, step, run, retry_feedback=""):
        """Build the input prompt for a step with template substitution."""
        template = step.get("prompt_template", "{trigger_payload}")
        prompt = template.replace("{trigger_payload}", str(run.get("trigger_payload", "")))

        # Build pipeline context from previous step outputs
        context_parts = []
        for sid, sdata in (run.get("step_outputs") or {} or {}).items():
            if isinstance(sdata, dict) and sdata.get("output"):
                context_parts.append(f"[{sid}]: {sdata['output'][:1000]}")
        pipeline_context = "\n\n".join(context_parts) if context_parts else "No previous context."
        prompt = prompt.replace("{pipeline_context}", pipeline_context)

        # Replace specific step output references
        for sid, sdata in (run.get("step_outputs") or {} or {}).items():
            if isinstance(sdata, dict):
                prompt = prompt.replace(f"{{{sid}_output}}", sdata.get("output", "")[:2000])

        if retry_feedback:
            prompt += f"\n\n## Retry Feedback:\n{retry_feedback}"

        return prompt

    async def _resolve_agent(self, agent_id):
        """Load agent config from DB or built-in models."""
        if agent_id and agent_id.startswith("nxa_"):
            agent = await self.db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0})
            if agent:
                return agent
        from nexus_config import AI_MODELS
        for m in AI_MODELS:
            if m.get("key") == agent_id:
                return {"base_model": agent_id, "system_prompt": m.get("system_prompt", "You are a helpful AI assistant."), "name": m.get("name", agent_id)}
        return {"base_model": agent_id, "system_prompt": "You are a helpful AI assistant.", "name": agent_id}

    async def _resolve_api_key(self, workspace_id, model_key):
        """Resolve API key for a model."""
        from key_resolver import get_integration_key
        key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY",
                    "deepseek": "DEEPSEEK_API_KEY", "mistral": "MISTRAL_API_KEY", "grok": "GROK_API_KEY",
                    "cohere": "COHERE_API_KEY", "perplexity": "PERPLEXITY_API_KEY"}
        env_key = key_map.get(model_key, "OPENAI_API_KEY")
        key = await get_integration_key(self.db, env_key)
        if key:
            return key
        # Fallback: check workspace owner's keys
        import os
        return os.environ.get(env_key, "")

    async def _notify_channel(self, pipeline, run_id, message):
        """Post a notification message to the pipeline's notification channel."""
        channel_id = (pipeline.get("settings") or {}).get("notification_channel_id")
        if not channel_id:
            return
        await self.db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": channel_id,
            "content": message, "sender_name": "A2A Pipeline", "sender_type": "system",
            "metadata": {"a2a_run_id": run_id}, "created_at": now_iso(),
        })

    async def _emit(self, run_id, event, payload):
        """Emit WebSocket event for real-time monitoring."""
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast(json.dumps({"type": event, "run_id": run_id, **payload}), channel=f"a2a:{run_id}")
            except Exception as _e:
                import logging; logging.getLogger("a2a_engine").warning(f"Suppressed: {_e}")

    async def _fail_run(self, run_id, error_msg):
        """Mark a run as failed."""
        await self.db.a2a_runs.update_one({"run_id": run_id}, {"$set": {
            "status": "failed", "error": error_msg, "completed_at": now_iso(),
        }})
        await self._emit(run_id, "pipeline:failed", {"error": error_msg})
        logger.warning(f"A2A run {run_id} failed: {error_msg}")
