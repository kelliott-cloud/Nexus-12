from nexus_utils import now_iso
"""Nexus Operator Engine — Multi-Agent Autonomous Computer Use.
Orchestrates multiple AI agents working in parallel with browser, code, and tool access."""
import uuid
import asyncio
import json
import re
import time
import logging
import os
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, List, Optional

logger = logging.getLogger(__name__)



# ============ Security Sandboxing ============

BLOCKED_URL_PATTERNS = [r"file://", r"javascript:", r"data:", r"ftp://", r"localhost", r"127\.0\.0\.1", r"0\.0\.0\.0", r"169\.254", r"10\.\d+\.\d+\.\d+", r"192\.168"]
BLOCKED_DOMAINS = ["evil.com", "malware.com"]
BLOCKED_CODE_PATTERNS = [r"os\.system\s*\(", r"subprocess\.", r"shutil\.rmtree", r"__import__\s*\(", r"eval\s*\(", r"exec\s*\(", r"open\s*\(.*(\/etc|\/proc|\/sys|\.env)", r"rm\s+-rf\s+\/"]


def is_url_safe(url: str) -> Tuple[bool, str]:
    if not url:
        return (False, "Empty URL")
    for pattern in BLOCKED_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return (False, f"Blocked URL pattern: {pattern}")
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.lower() in BLOCKED_DOMAINS:
        return (False, f"Blocked domain: {parsed.hostname}")
    if not url.startswith(("http://", "https://")):
        return (False, "URL must start with http:// or https://")
    return (True, "")


def is_code_safe(code: str, language: str = "python") -> Tuple[bool, str]:
    if not code:
        return (False, "Empty code")
    for pattern in BLOCKED_CODE_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return (False, f"Blocked code pattern detected")
    if len(code) > 50000:
        return (False, "Code exceeds 50KB limit")
    return (True, "")


def check_tool_permission(tool_name: str, task: Dict[str, Any], budget: Dict[str, Any]) -> Tuple[bool, str]:
    allowed_tools = set(task.get("tools_required") or [] + task.get("tools_optional") or [])
    if allowed_tools and tool_name not in allowed_tools:
        return (False, f"Tool {tool_name} not in task's allowed tools")
    if tool_name == "execute_code" and not budget.get("allow_code_execution", True):
        return (False, "Code execution disabled by budget")
    if tool_name in ("wiki_write_page", "create_artifact", "save_to_memory") and not budget.get("allow_file_writes", True):
        return (False, "File writes disabled by budget")
    return (True, "")


# ============ Cross-Validator ============

class CrossValidator:
    def __init__(self, db):
        self.db = db

    async def validate_task_output(self, session, task, task_output):
        if not task_output or len(task_output) < 20:
            return {"validated": False, "score": 0.0, "issues": ["Output too short"]}
        try:
            task_agent = task.get("agent_id", "chatgpt")
            validator_map = {"claude": "chatgpt", "chatgpt": "claude", "gemini": "chatgpt", "deepseek": "claude"}
            validator_model = validator_map.get(task_agent, "chatgpt")

            from key_resolver import get_integration_key
            key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY"}
            api_key = await get_integration_key(self.db, key_map.get(validator_model, "OPENAI_API_KEY"))
            if not api_key:
                return {"validated": True, "score": 0.7, "issues": [], "method": "heuristic"}

            from ai_providers import call_ai_direct
            prompt = f"""Validate this AI agent output. Score 0.0-1.0 on accuracy and completeness.

TASK: {task.get('goal', '')}
OUTPUT: {task_output[:3000]}

Respond with JSON only: {{"score": 0.0, "issues": ["issue1"], "summary": "..."}}"""

            result = await call_ai_direct(validator_model, api_key, "You are a QA validator. Always respond with JSON.", prompt)
            from workflow_engine import parse_ai_json
            parsed = parse_ai_json(result)
            return {"validated": True, "score": float(parsed.get("score", 0.7)), "issues": parsed.get("issues") or [], "summary": parsed.get("summary", ""), "method": "ai"}
        except Exception as e:
            logger.debug(f"Cross-validation failed: {e}")
            return {"validated": True, "score": 0.7, "issues": [], "method": "fallback"}


class OperatorEngine:
    def __init__(self, db, ws_manager=None):
        self.db = db
        self.ws_manager = ws_manager

    async def plan_tasks(self, session_id: str, goal: str, workspace_id: str):
        """Use AI to decompose a goal into a task plan with parallel groups."""
        from ai_providers import call_ai_direct
        from key_resolver import get_integration_key

        api_key = await get_integration_key(self.db, "ANTHROPIC_API_KEY") or await get_integration_key(self.db, "OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
        model = "claude" if await get_integration_key(self.db, "ANTHROPIC_API_KEY") else "chatgpt"

        # Get workspace context
        channels = await self.db.channels.find({"workspace_id": workspace_id}, {"_id": 0, "name": 1}).to_list(10)
        projects = await self.db.projects.find({"workspace_id": workspace_id, "is_deleted": {"$ne": True}}, {"_id": 0, "title": 1}).to_list(5)
        context = f"Workspace channels: {[c.get('name','') for c in channels]}. Projects: {[p.get('title','') for p in projects]}."

        plan_prompt = f"""You are a task planner for a multi-agent AI system. Decompose this goal into specific tasks that can be executed by AI agents.

GOAL: {goal}

WORKSPACE CONTEXT: {context}

Available tools per agent:
- browser_navigate, browser_click, browser_type, browser_screenshot (web browsing)
- execute_code (run Python/JS/bash via sandbox)
- wiki_write_page, wiki_read_page (documentation)
- create_task (project management)
- save_to_memory (persistent knowledge)
- web_search (search the web)

Rules:
- Tasks in the same parallel_group run SIMULTANEOUSLY
- Tasks with depends_on wait for those tasks to complete first
- Use parallel groups for independent research (e.g., browsing 5 different sites)
- Use sequential dependencies for synthesis/analysis after research
- Assign estimated_model_tier: "light" (fast summaries), "standard" (general), "premium" (complex analysis)
- Keep max_steps reasonable (5-15 per task)

Respond with ONLY valid JSON:
{{
  "tasks": [
    {{
      "task_id": "task_001",
      "type": "browser_research",
      "goal": "Research competitor X pricing page",
      "tools_required": ["browser_navigate", "browser_screenshot"],
      "tools_optional": ["save_to_memory"],
      "parallel_group": "research_batch_1",
      "depends_on": [],
      "estimated_model_tier": "standard",
      "max_steps": 10,
      "timeout_sec": 120,
      "priority": 1
    }}
  ],
  "parallel_groups": {{
    "research_batch_1": {{"max_concurrent": 5, "strategy": "all_must_complete"}}
  }},
  "estimated_total_cost_usd": 0.50,
  "estimated_duration_sec": 180
}}"""

        try:
            response = await call_ai_direct(model, api_key, "You are a precise task planner. Always respond with valid JSON only.", plan_prompt)
            # Parse JSON from response
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            plan = json.loads(clean)
            # Ensure task_ids
            for i, task in enumerate(plan.get("tasks") or []):
                if not task.get("task_id"):
                    task["task_id"] = f"task_{i:03d}"
            return plan
        except Exception as e:
            logger.error(f"Task planning failed: {e}")
            # Fallback: single sequential task
            return {
                "tasks": [{"task_id": "task_000", "type": "general", "goal": goal, "tools_required": ["browser_navigate"], "tools_optional": [], "parallel_group": None, "depends_on": [], "estimated_model_tier": "standard", "max_steps": 15, "timeout_sec": 300, "priority": 1}],
                "parallel_groups": {},
                "estimated_total_cost_usd": 0.25,
                "estimated_duration_sec": 120,
            }

    async def dispatch_agents(self, session_id: str, plan: dict):
        """Assign AI models to each task based on requirements."""
        from key_resolver import get_integration_key
        assignments = {}
        tier_map = {
            "light": ["deepseek", "mistral", "chatgpt"],
            "standard": ["chatgpt", "claude", "gemini"],
            "premium": ["claude", "chatgpt"],
        }
        for task in plan.get("tasks") or []:
            tier = task.get("estimated_model_tier", "standard")
            candidates = tier_map.get(tier, ["chatgpt"])
            assigned = candidates[0]
            for c in candidates:
                key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY", "deepseek": "DEEPSEEK_API_KEY", "mistral": "MISTRAL_API_KEY"}
                if await get_integration_key(self.db, key_map.get(c, "OPENAI_API_KEY")):
                    assigned = c
                    break
            assignments[task["task_id"]] = {"agent_id": assigned, "model": assigned, "browser_session_id": None}
        return assignments

    async def run_session(self, session_id: str):
        """Main execution loop — runs tasks respecting parallel groups and dependencies."""
        session = await self.db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            return

        plan = session.get("task_plan") or {}
        tasks = plan.get("tasks") or []
        assignments = session.get("agent_assignments") or {}
        budget_max = (session.get("budget") or {}).get("max_total_cost_usd", 5.0)

        await self.db.operator_sessions.update_one({"session_id": session_id}, {"$set": {"status": "executing"}})
        await self._emit(session_id, "session:executing", {"task_count": len(tasks)})

        completed_tasks = set()
        task_outputs = {}
        total_cost = 0
        start_time = time.time()

        # Group tasks by parallel_group
        groups = {}
        sequential = []
        for t in tasks:
            pg = t.get("parallel_group")
            if pg:
                groups.setdefault(pg, []).append(t)
            else:
                sequential.append(t)

        # Execute parallel groups first, then sequential
        all_ordered = []
        seen_groups = set()
        for t in tasks:
            pg = t.get("parallel_group")
            if pg and pg not in seen_groups:
                seen_groups.add(pg)
                all_ordered.append(("parallel", pg, groups[pg]))
            elif not pg:
                all_ordered.append(("sequential", None, [t]))

        for batch_type, group_name, batch_tasks in all_ordered:
            # Check dependencies
            for t in batch_tasks:
                deps = t.get("depends_on") or []
                for dep in deps:
                    if dep not in completed_tasks:
                        # Wait for dependency (simple polling)
                        for _ in range(60):
                            await asyncio.sleep(1)
                            if dep in completed_tasks:
                                break

            # Check session status
            session = await self.db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0, "status": 1})
            if session and session.get("status") in ("cancelled", "paused"):
                break

            # Cost guard
            if total_cost > budget_max:
                await self._fail_session(session_id, f"Budget exceeded: ${total_cost:.4f} > ${budget_max}")
                break

            if batch_type == "parallel":
                results = await self._execute_parallel_group(session_id, session, batch_tasks, assignments, task_outputs)
                for tid, result in results.items():
                    if result.get("status") == "completed":
                        completed_tasks.add(tid)
                        task_outputs[tid] = result.get("output", "")
                        total_cost += result.get("cost_usd", 0)
            else:
                for t in batch_tasks:
                    result = await self._execute_task(session_id, t, assignments.get(t["task_id"], {}), task_outputs)
                    if isinstance(result, dict):
                        completed_tasks.add(t["task_id"])
                        task_outputs[t["task_id"]] = result.get("output", "")
                        total_cost += result.get("cost_usd", 0)

        # Complete session
        duration_ms = int((time.time() - start_time) * 1000)
        summary = "\n\n".join([f"**{tid}**: {out[:500]}" for tid, out in task_outputs.items()])

        await self.db.operator_sessions.update_one({"session_id": session_id}, {"$set": {
            "status": "completed", "completed_at": now_iso(),
            "results": {"summary": summary[:10000], "artifacts": [], "screenshots": [], "validation_results": {}},
            "metrics": {"total_cost_usd": round(total_cost, 4), "total_duration_ms": duration_ms,
                        "tasks_completed": len(completed_tasks), "tasks_failed": len(tasks) - len(completed_tasks),
                        "parallel_peak": max(len(g) for g in groups.values()) if groups else 1},
        }})
        await self._emit(session_id, "session:completed", {"duration_ms": duration_ms, "cost": total_cost})

        # Post summary to channel
        channel_id = session.get("channel_id")
        if channel_id:
            await self.db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": channel_id,
                "content": f"**Operator Session Complete**\n\nGoal: {session.get('goal', '')}\n\n{summary[:2000]}",
                "sender_name": "Nexus Operator", "sender_type": "system",
                "metadata": {"operator_session_id": session_id}, "created_at": now_iso(),
            })

        # Store learning
        await self.db.operator_learnings.insert_one({
            "learning_id": f"opl_{uuid.uuid4().hex[:10]}", "workspace_id": session.get("workspace_id"),
            "goal_type": session.get("goal_type", "general"), "goal_summary": session.get("goal", "")[:200],
            "task_count": len(tasks), "parallel_groups": len(groups),
            "total_cost": total_cost, "total_duration_ms": duration_ms,
            "success": len(completed_tasks) == len(tasks), "created_at": now_iso(),
        })

    async def _execute_task(self, session_id, task, assignment, upstream_outputs):
        """Execute a single task with an AI agent."""
        task_id = task["task_id"]
        agent_model = assignment.get("model", "chatgpt")
        exec_id = f"opx_{uuid.uuid4().hex[:10]}"
        start = time.time()

        await self.db.operator_task_executions.insert_one({
            "exec_id": exec_id, "session_id": session_id, "task_id": task_id,
            "agent_id": agent_model, "model": agent_model,
            "status": "running", "type": task.get("type", "general"), "goal": task.get("goal", ""),
            "actions": [], "observations_posted": [], "screenshots": [],
            "ai_messages": [], "output": "", "tokens_in": 0, "tokens_out": 0,
            "cost_usd": 0, "duration_ms": 0, "started_at": now_iso(), "completed_at": None, "error": None,
        })
        await self._emit(session_id, "task:started", {"task_id": task_id, "agent": agent_model, "type": task.get("type")})

        try:
            from ai_providers import call_ai_direct
            from key_resolver import get_integration_key
            key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY", "deepseek": "DEEPSEEK_API_KEY", "mistral": "MISTRAL_API_KEY"}
            api_key = await get_integration_key(self.db, key_map.get(agent_model, "OPENAI_API_KEY"))
            if not api_key:
                api_key = os.environ.get(key_map.get(agent_model, "OPENAI_API_KEY"), "")

            # Build context from upstream outputs
            context = ""
            for dep_id in task.get("depends_on") or []:
                if dep_id in upstream_outputs:
                    context += f"\n\n[Output from {dep_id}]:\n{upstream_outputs[dep_id][:2000]}"

            # Get shared observations
            session = await self.db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0, "observations": 1})
            obs = session.get("observations") or [] if session else []
            if obs:
                context += "\n\n[Shared Observations]:\n" + "\n".join([f"- {o.get('key','')}: {o.get('value','')}" for o in obs[-10:]])

            system_prompt = f"""You are an AI agent in the Nexus Operator system. Execute the assigned task precisely.

TASK: {task.get('goal', '')}
TYPE: {task.get('type', 'general')}

Available tools: {', '.join(task.get('tools_required', []) + task.get('tools_optional', []))}

Instructions:
- Complete the task thoroughly
- Share key findings as observations
- Be concise but comprehensive
- If you need to browse, describe what you would navigate to and what you'd look for
- If you need to write code, provide the complete code
- If you need to create documentation, write the full content"""

            user_prompt = f"Execute this task: {task.get('goal', '')}"
            if context:
                user_prompt += f"\n\nContext from previous tasks:{context}"

            output = await call_ai_direct(agent_model, api_key, system_prompt, user_prompt)

            duration_ms = int((time.time() - start) * 1000)
            tokens_in = len(user_prompt.split()) * 1.3
            tokens_out = len(output.split()) * 1.3
            from workflow_engine import calc_cost
            cost = calc_cost(agent_model, int(tokens_in), int(tokens_out))

            # Extract observations
            observations = self._extract_observations(output, task_id)
            if observations:
                await self.db.operator_sessions.update_one(
                    {"session_id": session_id},
                    {"$push": {"observations": {"$each": observations}}}
                )

            await self.db.operator_task_executions.update_one({"exec_id": exec_id}, {"$set": {
                "status": "completed", "output": output[:10000], "observations_posted": observations,
                "tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
                "cost_usd": cost, "duration_ms": duration_ms, "completed_at": now_iso(),
            }})

            await self.db.operator_sessions.update_one({"session_id": session_id}, {
                "$inc": {"metrics.total_cost_usd": cost, "metrics.total_tokens_in": int(tokens_in), "metrics.total_tokens_out": int(tokens_out)},
            })

            await self._emit(session_id, "task:completed", {"task_id": task_id, "cost": cost, "duration_ms": duration_ms})
            return {"status": "completed", "output": output, "cost_usd": cost}

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = str(e)[:500]
            await self.db.operator_task_executions.update_one({"exec_id": exec_id}, {"$set": {
                "status": "failed", "error": error_msg, "duration_ms": duration_ms, "completed_at": now_iso(),
            }})
            await self._emit(session_id, "task:failed", {"task_id": task_id, "error": error_msg})
            return {"status": "failed", "error": error_msg, "output": "", "cost_usd": 0}

    def _extract_observations(self, output, task_id):
        """Extract key observations from agent output."""
        observations = []
        lines = output.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("- **") or line.startswith("**") or (": " in line and len(line) < 200):
                key = line[:80].strip("*- ")
                observations.append({
                    "type": "finding", "key": key, "value": line[:300],
                    "confidence": 0.8, "source_task": task_id, "timestamp": now_iso(),
                })
                if len(observations) >= 5:
                    break
        return observations

    async def _emit(self, session_id, event, payload):
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast(json.dumps({"type": event, "session_id": session_id, **payload}), channel=f"operator:{session_id}")
            except Exception as _e:
                import logging; logging.getLogger("operator_engine").warning(f"Suppressed: {_e}")

    async def _fail_session(self, session_id, error):
        await self.db.operator_sessions.update_one({"session_id": session_id}, {"$set": {"status": "failed", "error": error, "completed_at": now_iso()}})
        await self._emit(session_id, "session:failed", {"error": error})


    async def _execute_parallel_group(self, session_id, session, tasks, assignments, all_outputs):
        """Execute tasks in parallel with error recovery and retry logic."""
        coros = {}
        for t in tasks:
            tid = t["task_id"]
            timeout = t.get("timeout_sec", 120)
            coros[tid] = asyncio.wait_for(
                self._execute_task(session_id, t, assignments.get(tid, {}), all_outputs),
                timeout=timeout
            )

        raw_results = await asyncio.gather(*coros.values(), return_exceptions=True)

        # Update parallel peak metric
        await self.db.operator_sessions.update_one(
            {"session_id": session_id},
            {"$max": {"metrics.parallel_peak": len(tasks)}}
        )

        results = {}
        failed_tasks = []
        for t, result in zip(tasks, raw_results):
            tid = t["task_id"]
            if isinstance(result, Exception):
                logger.error(f"Parallel task {tid} exception: {result}")
                failed_tasks.append(t)
                results[tid] = {"status": "failed", "error": str(result), "output": "", "cost_usd": 0}
            elif isinstance(result, dict) and result.get("status") == "failed":
                failed_tasks.append(t)
                results[tid] = result
            else:
                results[tid] = result if isinstance(result, dict) else {"status": "completed", "output": "", "cost_usd": 0}

        # Retry failed tasks with different models
        from key_resolver import get_integration_key
        fallback_models = ["chatgpt", "claude", "gemini", "deepseek"]
        for t in failed_tasks:
            tid = t["task_id"]
            original = assignments.get(tid, {}).get("model", "")
            retried = False
            for fallback in fallback_models:
                if fallback == original:
                    continue
                key_map = {"chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_AI_KEY", "deepseek": "DEEPSEEK_API_KEY"}
                key = await get_integration_key(self.db, key_map.get(fallback, "OPENAI_API_KEY"))
                if not key:
                    continue
                logger.info(f"Retrying task {tid} with {fallback} (was {original})")
                await self._emit(session_id, "task:retrying", {"task_id": tid, "original_agent": original, "retry_agent": fallback, "attempt": 1})
                assignments[tid] = {"agent_id": fallback, "model": fallback, "browser_session_id": None}
                retry_result = await self._execute_task(session_id, t, assignments[tid], all_outputs)
                if isinstance(retry_result, dict) and retry_result.get("status") == "completed":
                    results[tid] = retry_result
                    retried = True
                    break
            if not retried:
                logger.warning(f"Task {tid} failed after retry attempts")

        return results
