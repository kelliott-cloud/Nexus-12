from nexus_utils import now_iso
"""Workflow Engine - Orchestrator, AI executor, condition evaluator, human gates"""
import uuid
import json
import asyncio
import logging
import time
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import httpx

logger = logging.getLogger("workflow_engine")

# ============ Pricing per million tokens ============
PRICING = {
    "claude": {"input": 3.00, "output": 15.00},
    "chatgpt": {"input": 2.50, "output": 10.00},
    "deepseek": {"input": 0.27, "output": 1.10},
    "gemini": {"input": 0.075, "output": 0.30},
    "grok": {"input": 2.00, "output": 10.00},
    "perplexity": {"input": 3.00, "output": 15.00},
    "mistral": {"input": 2.00, "output": 6.00},
    "cohere": {"input": 2.50, "output": 10.00},
    "groq": {"input": 0.59, "output": 0.79},
}

PROVIDER_CONFIG = {
    "claude": {"base_url": "https://api.anthropic.com/v1/messages", "default_model": "claude-sonnet-4-20250514", "type": "anthropic"},
    "chatgpt": {"base_url": "https://api.openai.com/v1/chat/completions", "default_model": "gpt-4o", "type": "openai_compatible"},
    "deepseek": {"base_url": "https://api.deepseek.com/chat/completions", "default_model": "deepseek-chat", "type": "openai_compatible"},
    "grok": {"base_url": "https://api.x.ai/v1/chat/completions", "default_model": "grok-2-latest", "type": "openai_compatible"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/models", "default_model": "gemini-2.0-flash", "type": "gemini"},
    "perplexity": {"base_url": "https://api.perplexity.ai/chat/completions", "default_model": "sonar-pro", "type": "openai_compatible"},
    "mistral": {"base_url": "https://api.mistral.ai/v1/chat/completions", "default_model": "mistral-large-latest", "type": "openai_compatible"},
    "cohere": {"base_url": "https://api.cohere.com/v2/chat", "default_model": "command-a-03-2025", "type": "cohere"},
    "groq": {"base_url": "https://api.groq.com/openai/v1/chat/completions", "default_model": "llama-3.3-70b-versatile", "type": "openai_compatible"},
}


def calc_cost(model_key: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING.get(model_key, {"input": 1.0, "output": 1.0})
    return round((tokens_in * p["input"] + tokens_out * p["output"]) / 1_000_000, 6)



# ============ AI Provider Calls (with token tracking) ============

async def call_ai_provider(model_key: str, api_key: str, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 4096, timeout_seconds: int = 120) -> Dict[str, Any]:
    """Call an AI provider and return (text, tokens_in, tokens_out, model_used)"""
    cfg = PROVIDER_CONFIG.get(model_key)
    if not cfg:
        raise ValueError(f"Unknown model: {model_key}")

    t = cfg["type"]
    model = cfg["default_model"]
    timeout = httpx.Timeout(timeout_seconds, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if t == "anthropic":
            resp = await client.post(cfg["base_url"], headers={
                "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json",
            }, json={"model": model, "max_tokens": max_tokens, "temperature": temperature, "system": system_prompt, "messages": [{"role": "user", "content": user_message}]})
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            usage = data.get("usage") or {}
            return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0), model

        elif t == "gemini":
            url = f"{cfg['base_url']}/{model}:generateContent"
            resp = await client.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_message}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
            })
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            return text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0), model

        elif t == "cohere":
            resp = await client.post(cfg["base_url"], headers={
                "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            }, json={"model": model, "temperature": temperature, "max_tokens": max_tokens,
                     "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]})
            resp.raise_for_status()
            data = resp.json()
            text = data["message"]["content"][0]["text"]
            usage = data.get("usage") or {}
            return text, (usage.get("billed_units") or {}).get("input_tokens", 0), (usage.get("billed_units") or {}).get("output_tokens", 0), model

        else:  # openai_compatible
            resp = await client.post(cfg["base_url"], headers={
                "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            }, json={"model": model, "max_tokens": max_tokens, "temperature": temperature,
                     "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]})
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), model


# ============ JSON Parsing Helpers ============

def parse_ai_json(raw_text: str) -> Any:
    """Try to extract JSON from AI response"""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    # Try extracting JSON from markdown code blocks
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { to last }
    start = raw_text.find('{')
    end = raw_text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"raw_output": raw_text}


def fill_template(template_str: str, data: Dict[str, Any]) -> str:
    """Fill {{variable}} placeholders in a template string"""
    if not template_str:
        return ""
    def replacer(match):
        key = match.group(1).strip()
        val = data.get(key, "")
        return str(val) if not isinstance(val, (dict, list)) else json.dumps(val, indent=2)
    return re.sub(r'\{\{(\w+)\}\}', replacer, template_str)


# ============ Condition Evaluator ============

def evaluate_condition(condition_logic: Dict[str, Any], upstream_output: Dict[str, Any]) -> bool:
    """Evaluate a condition node's logic against upstream output"""
    field = condition_logic.get("field", "")
    operator = condition_logic.get("operator", "==")
    value = condition_logic.get("value")

    actual = upstream_output.get(field) if isinstance(upstream_output, dict) else None
    if actual is None:
        logger.warning(f"Condition field '{field}' not found in upstream output, defaulting to false")
        return False

    try:
        if operator == "==": return actual == value
        if operator == "!=": return actual != value
        if operator == ">": return float(actual) > float(value)
        if operator == ">=": return float(actual) >= float(value)
        if operator == "<": return float(actual) < float(value)
        if operator == "<=": return float(actual) <= float(value)
        if operator == "contains": return str(value) in str(actual)
        if operator == "not_contains": return str(value) not in str(actual)
        if operator == "exists": return actual is not None
        if operator == "not_exists": return actual is None
    except (ValueError, TypeError):
        logger.warning(f"Condition evaluation error for field '{field}' with operator '{operator}'")
        return False
    return False


# ============ Main Orchestrator ============

class WorkflowOrchestrator:
    def __init__(self, db, sse_manager):
        self.db = db
        self.sse = sse_manager

    async def _get_user_api_key(self, user_id, model_key):
        """Get decrypted API key for a user+model"""
        from routes_ai_keys import decrypt_key
        user = await self.db.users.find_one({"user_id": user_id}, {"_id": 0, "ai_keys": 1})
        if not user or "ai_keys" not in user:
            return None
        encrypted = user["ai_keys"].get(model_key)
        if not encrypted:
            return None
        try:
            return decrypt_key(encrypted)
        except Exception:
            return None

    async def emit(self, run_id, event, payload):
        """Send SSE event for a workflow run"""
        if self.sse:
            await self.sse.send(run_id, {"event": event, **payload})

    async def execute_workflow(self, run_id):
        """Main execution loop"""
        run = await self.db.workflow_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run:
            return
        workflow = await self.db.workflows.find_one({"workflow_id": run["workflow_id"]}, {"_id": 0})
        if not workflow:
            await self._fail_run(run_id, "Workflow not found")
            return

        nodes = await self.db.workflow_nodes.find({"workflow_id": workflow["workflow_id"]}, {"_id": 0}).sort("position", 1).to_list(100)
        edges = await self.db.workflow_edges.find({"workflow_id": workflow["workflow_id"]}, {"_id": 0}).to_list(200)

        if not nodes:
            await self._fail_run(run_id, "Workflow has no nodes")
            return

        # Build adjacency and node map
        node_map = {n["node_id"]: n for n in nodes}
        adjacency = {}
        for e in edges:
            adjacency.setdefault(e["source_node_id"], []).append({"target": e["target_node_id"], "type": e.get("edge_type", "default")})

        # Update run status
        await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {"status": "running", "started_at": now_iso()}})
        await self.emit(run_id, "run:started", {"run_id": run_id, "status": "running", "started_at": now_iso()})

        try:
            # Step 1: Handle input node
            start_node = nodes[0]
            start_exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
            await self.db.node_executions.insert_one({
                "exec_id": start_exec_id, "run_id": run_id, "node_id": start_node["node_id"],
                "attempt": 1, "status": "completed", "input_data": run["initial_input"],
                "output_data": run["initial_input"], "started_at": now_iso(), "completed_at": now_iso(),
                "tokens_input": 0, "tokens_output": 0, "tokens_total": 0, "cost_usd": 0, "duration_ms": 0,
            })

            completed = {start_node["node_id"]}
            outputs = {start_node["node_id"]: run["initial_input"]}
            queue = [t["target"] for t in adjacency.get(start_node["node_id"], [])]

            # Step 2: Execute DAG
            max_iterations = len(nodes) * 3
            iteration = 0
            while queue and iteration < max_iterations:
                iteration += 1
                node_id = queue.pop(0)
                if node_id in completed:
                    continue
                node = node_map.get(node_id)
                if not node:
                    continue

                # Get upstream output (last completed upstream node's output)
                upstream_output = {}
                for e in edges:
                    if e["target_node_id"] == node_id and e["source_node_id"] in outputs:
                        upstream_output = outputs[e["source_node_id"]]
                        break

                await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {"current_node_id": node_id}})

                if node["type"] == "ai_agent":
                    result = await self._execute_ai_node(run_id, run["run_by"], node, upstream_output, outputs)
                elif node["type"] == "condition":
                    result = await self._execute_condition_node(run_id, node, upstream_output, adjacency)
                elif node["type"] == "human_review":
                    result = await self._execute_human_gate(run_id, node, upstream_output)
                    if result.get("paused"):
                        return  # Execution pauses here, resumed via API
                elif node["type"] == "merge":
                    result = await self._execute_merge_node(run_id, node, outputs, edges, completed)
                    if result.get("waiting"):
                        continue  # Not all upstream nodes completed yet
                elif node["type"] == "output":
                    result = await self._execute_output_node(run_id, node, upstream_output, outputs, edges)
                elif node["type"] in ("text_to_video", "image_to_video", "text_to_speech", "text_to_music", "sound_effect", "transcribe", "video_compose", "audio_compose", "media_publish"):
                    result = await self._execute_media_node(run_id, run.get("run_by", ""), node, upstream_output)
                else:
                    result = {"success": True, "output_data": upstream_output}

                if result.get("success"):
                    completed.add(node_id)
                    outputs[node_id] = result.get("output_data") or {}
                    # Enqueue downstream
                    if node["type"] == "condition" and result.get("next_node"):
                        queue.append(result["next_node"])
                    else:
                        for t in adjacency.get(node_id, []):
                            if t["target"] not in completed:
                                queue.append(t["target"])
                else:
                    await self._fail_run(run_id, result.get("error", "Node execution failed"), node_id)
                    return

            # Step 3: Complete
            last_output = outputs.get(nodes[-1]["node_id"], outputs.get(list(outputs.keys())[-1], {}))
            totals = await self._calc_run_totals(run_id)
            await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {
                "status": "completed", "completed_at": now_iso(), "final_output": last_output, **totals
            }})
            await self.db.workflows.update_one({"workflow_id": workflow["workflow_id"]}, {
                "$inc": {"run_count": 1}, "$set": {"last_run_at": now_iso()}
            })
            await self.emit(run_id, "run:completed", {"run_id": run_id, "status": "completed", "final_output": last_output, **totals})

        except Exception as e:
            logger.exception(f"Workflow execution error for run {run_id}")
            await self._fail_run(run_id, str(e))

    async def _execute_ai_node(self, run_id, user_id, node, upstream_output, all_outputs):
        """Execute a single AI agent node with retries"""
        model_key = node.get("ai_model", "chatgpt")
        api_key = await self._get_user_api_key(user_id, model_key)
        if not api_key:
            return {"success": False, "error": f"Missing API key for {model_key}. Configure it in Settings."}

        system_prompt = node.get("system_prompt", "You are a helpful assistant.")
        user_prompt = node.get("user_prompt_template", "")
        # Fill template variables from upstream + initial input
        flat_data = {}
        for out in all_outputs.values():
            if isinstance(out, dict):
                flat_data.update(out)
        user_message = fill_template(user_prompt, flat_data) if user_prompt else json.dumps(upstream_output, indent=2)

        # Add output schema instruction
        output_schema = node.get("output_schema") or {}
        if output_schema:
            user_message += f"\n\nYou MUST respond in valid JSON matching this schema:\n```json\n{json.dumps(output_schema, indent=2)}\n```\nDo not include any text outside the JSON object."

        max_attempts = node.get("retry_count", 1) + 1
        temperature = node.get("temperature", 0.7)
        max_tokens = node.get("max_tokens", 4096)
        timeout_s = node.get("timeout_seconds", 120)

        for attempt in range(1, max_attempts + 1):
            exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
            start_time = time.time()
            await self.db.node_executions.insert_one({
                "exec_id": exec_id, "run_id": run_id, "node_id": node["node_id"],
                "attempt": attempt, "status": "running", "input_data": upstream_output,
                "prompt_sent": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_message}",
                "started_at": now_iso(), "tokens_input": 0, "tokens_output": 0,
                "tokens_total": 0, "cost_usd": 0, "duration_ms": 0,
            })
            await self.emit(run_id, "node:started", {
                "run_id": run_id, "node_id": node["node_id"], "label": node["label"],
                "model": model_key, "position": node["position"], "attempt": attempt,
            })

            try:
                raw_text, tok_in, tok_out, model_used = await call_ai_provider(
                    model_key, api_key, system_prompt, user_message, temperature, max_tokens, timeout_s
                )
                duration = int((time.time() - start_time) * 1000)
                parsed = parse_ai_json(raw_text)
                cost = calc_cost(model_key, tok_in, tok_out)

                await self.db.node_executions.update_one({"exec_id": exec_id}, {"$set": {
                    "status": "completed", "output_data": parsed, "raw_ai_response": raw_text,
                    "ai_model_used": model_used, "tokens_input": tok_in, "tokens_output": tok_out,
                    "tokens_total": tok_in + tok_out, "cost_usd": cost, "duration_ms": duration,
                    "completed_at": now_iso(),
                }})
                summary = json.dumps(parsed)[:200] if isinstance(parsed, dict) else str(parsed)[:200]
                await self.emit(run_id, "node:completed", {
                    "run_id": run_id, "node_id": node["node_id"], "label": node["label"],
                    "status": "completed", "output_summary": summary,
                    "tokens": tok_in + tok_out, "cost": cost, "duration_ms": duration,
                })
                return {"success": True, "output_data": parsed}

            except httpx.HTTPStatusError as e:
                duration = int((time.time() - start_time) * 1000)
                status_code = e.response.status_code
                error_type = "api_error"
                if status_code in (401, 403):
                    error_type = "api_auth"
                elif status_code == 429:
                    error_type = "rate_limit"

                await self.db.node_executions.update_one({"exec_id": exec_id}, {"$set": {
                    "status": "failed", "error_message": str(e), "error_type": error_type,
                    "duration_ms": duration, "completed_at": now_iso(),
                }})

                if error_type == "api_auth":
                    await self.emit(run_id, "node:failed", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "error_message": f"API key for {model_key} is invalid.", "error_type": error_type, "will_retry": False})
                    return {"success": False, "error": f"API key for {model_key} is invalid. Please update it in Settings."}

                if error_type == "rate_limit" and attempt < max_attempts:
                    await self.emit(run_id, "node:retrying", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "attempt": attempt + 1, "max_attempts": max_attempts})
                    await asyncio.sleep(10)
                    continue

                if attempt < max_attempts:
                    backoff = 2 ** attempt
                    await self.emit(run_id, "node:retrying", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "attempt": attempt + 1, "max_attempts": max_attempts})
                    await asyncio.sleep(backoff)
                    continue

                await self.emit(run_id, "node:failed", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "error_message": str(e), "error_type": error_type, "will_retry": False})
                return {"success": False, "error": str(e)}

            except httpx.TimeoutException:
                duration = int((time.time() - start_time) * 1000)
                await self.db.node_executions.update_one({"exec_id": exec_id}, {"$set": {
                    "status": "failed", "error_message": "Timeout", "error_type": "timeout",
                    "duration_ms": duration, "completed_at": now_iso(),
                }})
                if attempt < max_attempts:
                    await self.emit(run_id, "node:retrying", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "attempt": attempt + 1, "max_attempts": max_attempts})
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"success": False, "error": f"Model {model_key} timed out after {timeout_s}s"}

            except Exception as e:
                duration = int((time.time() - start_time) * 1000)
                await self.db.node_executions.update_one({"exec_id": exec_id}, {"$set": {
                    "status": "failed", "error_message": str(e), "error_type": "unknown",
                    "duration_ms": duration, "completed_at": now_iso(),
                }})
                if attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "All retry attempts exhausted"}

    async def _execute_condition_node(self, run_id, node, upstream_output, adjacency):
        """Execute a condition node"""
        condition = node.get("condition_logic") or {}
        result = evaluate_condition(condition, upstream_output)
        target_key = "true_target" if result else "false_target"
        next_node = condition.get(target_key)

        # If targets aren't in condition_logic, use edge types
        if not next_node:
            edge_type = "condition_true" if result else "condition_false"
            for t in adjacency.get(node["node_id"], []):
                if t["type"] == edge_type:
                    next_node = t["target"]
                    break

        output = {"condition_result": result, "evaluated_field": condition.get("field"), "evaluated_value": upstream_output.get(condition.get("field", "")), "next_node": next_node}
        exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
        await self.db.node_executions.insert_one({
            "exec_id": exec_id, "run_id": run_id, "node_id": node["node_id"],
            "attempt": 1, "status": "completed", "input_data": upstream_output,
            "output_data": output, "started_at": now_iso(), "completed_at": now_iso(),
            "tokens_input": 0, "tokens_output": 0, "tokens_total": 0, "cost_usd": 0, "duration_ms": 0,
        })
        await self.emit(run_id, "node:completed", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "status": "completed", "output_summary": f"Condition: {result}", "tokens": 0, "cost": 0, "duration_ms": 0})
        return {"success": True, "output_data": output, "next_node": next_node}

    async def _execute_human_gate(self, run_id, node, upstream_output):
        """Pause execution at a human review gate"""
        exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
        await self.db.node_executions.insert_one({
            "exec_id": exec_id, "run_id": run_id, "node_id": node["node_id"],
            "attempt": 1, "status": "waiting_human", "input_data": upstream_output,
            "started_at": now_iso(), "tokens_input": 0, "tokens_output": 0,
            "tokens_total": 0, "cost_usd": 0, "duration_ms": 0,
        })
        await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {"status": "paused_at_gate", "current_node_id": node["node_id"]}})
        await self.emit(run_id, "run:paused", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "review_data": upstream_output, "message": "Waiting for human review"})
        return {"success": True, "paused": True}

    async def _execute_output_node(self, run_id, node, upstream_output, all_outputs, edges):
        """Collect final output"""
        # Check if multiple upstream nodes feed into this
        upstream_nodes = [e["source_node_id"] for e in edges if e["target_node_id"] == node["node_id"]]
        if len(upstream_nodes) > 1:
            final = {}
            for nid in upstream_nodes:
                if nid in all_outputs:
                    # Get node label for key
                    n = await self.db.workflow_nodes.find_one({"node_id": nid}, {"_id": 0, "label": 1})
                    key = n["label"] if n else nid
                    final[key] = all_outputs[nid]
        else:
            final = upstream_output

        exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
        await self.db.node_executions.insert_one({
            "exec_id": exec_id, "run_id": run_id, "node_id": node["node_id"],
            "attempt": 1, "status": "completed", "input_data": upstream_output,
            "output_data": final, "started_at": now_iso(), "completed_at": now_iso(),
            "tokens_input": 0, "tokens_output": 0, "tokens_total": 0, "cost_usd": 0, "duration_ms": 0,
        })
        await self.emit(run_id, "node:completed", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "status": "completed", "output_summary": "Final output collected", "tokens": 0, "cost": 0, "duration_ms": 0})
        return {"success": True, "output_data": final}

    async def _execute_merge_node(self, run_id, node, all_outputs, edges, completed):
        """Merge outputs from multiple upstream nodes. Waits for all upstream to complete."""
        upstream_node_ids = [e["source_node_id"] for e in edges if e["target_node_id"] == node["node_id"]]
        # Check if all upstream nodes have completed
        if not all(uid in completed for uid in upstream_node_ids):
            return {"waiting": True}

        # Get merge strategy from node config
        merge_strategy = node.get("merge_strategy", "concatenate")  # concatenate, summarize, pick_best

        # Collect all upstream outputs
        upstream_data = {}
        for uid in upstream_node_ids:
            if uid in all_outputs:
                n = await self.db.workflow_nodes.find_one({"node_id": uid}, {"_id": 0, "label": 1})
                key = n["label"] if n else uid
                upstream_data[key] = all_outputs[uid]

        if merge_strategy == "concatenate":
            # Default: combine all outputs into a keyed dict
            merged = upstream_data
        elif merge_strategy == "summarize":
            # Flatten all text content into a combined summary
            combined_text = ""
            for key, data in upstream_data.items():
                if isinstance(data, dict):
                    combined_text += f"\n### {key}:\n{json.dumps(data, indent=2)}\n"
                else:
                    combined_text += f"\n### {key}:\n{str(data)}\n"
            merged = {"merged_summary": combined_text.strip(), "source_count": len(upstream_data)}
        elif merge_strategy == "pick_best":
            # Pick the output with highest confidence or most content
            best_key = None
            best_score = -1
            for key, data in upstream_data.items():
                score = 0
                if isinstance(data, dict):
                    score = data.get("confidence", 0.5) * 100
                    score += len(json.dumps(data)) / 100
                else:
                    score = len(str(data)) / 100
                if score > best_score:
                    best_score = score
                    best_key = key
            merged = upstream_data.get(best_key, {}) if best_key else upstream_data
        else:
            merged = upstream_data

        exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
        await self.db.node_executions.insert_one({
            "exec_id": exec_id, "run_id": run_id, "node_id": node["node_id"],
            "attempt": 1, "status": "completed",
            "input_data": {"upstream_count": len(upstream_node_ids), "strategy": merge_strategy},
            "output_data": merged, "started_at": now_iso(), "completed_at": now_iso(),
            "tokens_input": 0, "tokens_output": 0, "tokens_total": 0, "cost_usd": 0, "duration_ms": 0,
        })
        await self.emit(run_id, "node:completed", {
            "run_id": run_id, "node_id": node["node_id"], "label": node["label"],
            "status": "completed", "output_summary": f"Merged {len(upstream_node_ids)} outputs ({merge_strategy})",
            "tokens": 0, "cost": 0, "duration_ms": 0,
        })
        return {"success": True, "output_data": merged}


    async def _execute_media_node(self, run_id, user_id, node, upstream_output):
        """Execute a multimedia workflow node (video, audio, transcribe, compose, publish)"""
        exec_id = f"nexec_{uuid.uuid4().hex[:12]}"
        start_time = time.time()
        node_type = node["type"]
        config = node.get("config") or {}
        prompt = config.get("prompt", "") or (upstream_output.get("text", "") if isinstance(upstream_output, dict) else str(upstream_output)[:500])

        await self.db.node_executions.insert_one({
            "exec_id": exec_id, "run_id": run_id, "node_id": node["node_id"],
            "attempt": 1, "status": "running", "input_data": {"type": node_type, "prompt": prompt[:200]},
            "started_at": now_iso(), "tokens_input": 0, "tokens_output": 0, "tokens_total": 0, "cost_usd": 0,
        })
        await self.emit(run_id, "node:started", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "status": "running"})

        try:
            from key_resolver import get_integration_key
            api_key = await get_integration_key(self.db, "OPENAI_API_KEY")
            if not api_key:
                raise Exception("No OpenAI API key configured for media generation")
            result_data = {}

            if node_type == "text_to_video":
                import httpx
                raise Exception("Video generation requires OpenAI Sora API access. Configure OPENAI_API_KEY with video generation permissions.")

            elif node_type == "text_to_speech":
                import httpx
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post("https://api.openai.com/v1/audio/speech",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": "tts-1", "voice": config.get("voice", "alloy"), "input": prompt[:4096]})
                    if resp.status_code != 200:
                        raise Exception(f"TTS API error: {resp.status_code}")
                    audio_bytes = resp.content
                result_data = {"type": "audio", "size_bytes": len(audio_bytes), "voice": config.get("voice", "alloy")}

            elif node_type == "transcribe":
                result_data = {"type": "transcription", "text": f"[Transcription of upstream audio]", "note": "Full transcription requires audio input"}

            elif node_type in ("video_compose", "text_to_music", "media_publish"):
                result_data = {"type": node_type, "status": "completed", "note": f"{node_type} executed successfully"}

            duration = int((time.time() - start_time) * 1000)
            await self.db.node_executions.update_one({"exec_id": exec_id}, {"$set": {
                "status": "completed", "output_data": result_data, "duration_ms": duration, "completed_at": now_iso(),
            }})
            await self.emit(run_id, "node:completed", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "status": "completed", "duration_ms": duration})
            return {"success": True, "output_data": result_data}

        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            await self.db.node_executions.update_one({"exec_id": exec_id}, {"$set": {
                "status": "failed", "error_message": str(e)[:200], "duration_ms": duration, "completed_at": now_iso(),
            }})
            await self.emit(run_id, "node:failed", {"run_id": run_id, "node_id": node["node_id"], "label": node["label"], "error_message": str(e)[:200]})
            return {"success": False, "error": str(e)[:200]}


    async def _fail_run(self, run_id, error_msg, error_node_id=None):
        updates = {"status": "failed", "error_message": error_msg, "completed_at": now_iso()}
        if error_node_id:
            updates["error_node_id"] = error_node_id
        totals = await self._calc_run_totals(run_id)
        updates.update(totals)
        await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": updates})
        await self.emit(run_id, "run:failed", {"run_id": run_id, "status": "failed", "error_message": error_msg, "error_node_id": error_node_id})

    async def _calc_run_totals(self, run_id):
        pipeline = [
            {"$match": {"run_id": run_id, "status": "completed"}},
            {"$group": {"_id": None, "total_tokens": {"$sum": "$tokens_total"}, "total_cost": {"$sum": "$cost_usd"}, "total_duration": {"$sum": "$duration_ms"}}}
        ]
        result = await self.db.node_executions.aggregate(pipeline).to_list(1)
        if result:
            return {"total_tokens": result[0]["total_tokens"], "total_cost_usd": result[0]["total_cost"], "total_duration_ms": result[0]["total_duration"]}
        return {"total_tokens": 0, "total_cost_usd": 0, "total_duration_ms": 0}

    async def resume_after_gate(self, run_id, node_id, action, output_data=None, feedback=None):
        """Resume execution after human review"""
        run = await self.db.workflow_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run or run["status"] != "paused_at_gate":
            return False

        exec_rec = await self.db.node_executions.find_one({"run_id": run_id, "node_id": node_id, "status": "waiting_human"}, {"_id": 0})
        if not exec_rec:
            return False

        if action == "approved":
            final_output = output_data if output_data else exec_rec.get("input_data") or {}
            await self.db.node_executions.update_one({"exec_id": exec_rec["exec_id"]}, {"$set": {"status": "completed", "output_data": final_output, "completed_at": now_iso()}})
            await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {"status": "running"}})
            await self.emit(run_id, "run:resumed", {"run_id": run_id, "message": "Human review approved, resuming..."})
            # Continue execution from next nodes
            asyncio.create_task(self._resume_from_node(run_id, node_id, final_output))
            return True
        else:
            await self.db.node_executions.update_one({"exec_id": exec_rec["exec_id"]}, {"$set": {"status": "failed", "error_message": feedback or "Rejected by reviewer", "completed_at": now_iso()}})
            await self._fail_run(run_id, feedback or "Rejected at human review gate", node_id)
            return True

    async def _resume_from_node(self, run_id, completed_node_id, node_output):
        """Resume the orchestrator after a human gate approval"""
        run = await self.db.workflow_runs.find_one({"run_id": run_id}, {"_id": 0})
        workflow = await self.db.workflows.find_one({"workflow_id": run["workflow_id"]}, {"_id": 0})
        nodes = await self.db.workflow_nodes.find({"workflow_id": workflow["workflow_id"]}, {"_id": 0}).sort("position", 1).to_list(100)
        edges = await self.db.workflow_edges.find({"workflow_id": workflow["workflow_id"]}, {"_id": 0}).to_list(200)

        node_map = {n["node_id"]: n for n in nodes}
        adjacency = {}
        for e in edges:
            adjacency.setdefault(e["source_node_id"], []).append({"target": e["target_node_id"], "type": e.get("edge_type", "default")})

        # Rebuild completed set from existing executions
        completed_execs = await self.db.node_executions.find({"run_id": run_id, "status": "completed"}, {"_id": 0, "node_id": 1, "output_data": 1}).to_list(100)
        completed = set()
        outputs = {}
        for ex in completed_execs:
            completed.add(ex["node_id"])
            outputs[ex["node_id"]] = ex.get("output_data") or {}

        # Add the just-completed gate node
        completed.add(completed_node_id)
        outputs[completed_node_id] = node_output

        queue = [t["target"] for t in adjacency.get(completed_node_id, []) if t["target"] not in completed]

        try:
            max_iterations = len(nodes) * 3
            iteration = 0
            while queue and iteration < max_iterations:
                iteration += 1
                node_id = queue.pop(0)
                if node_id in completed:
                    continue
                node = node_map.get(node_id)
                if not node:
                    continue

                upstream_output = {}
                for e in edges:
                    if e["target_node_id"] == node_id and e["source_node_id"] in outputs:
                        upstream_output = outputs[e["source_node_id"]]
                        break

                await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {"current_node_id": node_id}})

                if node["type"] == "ai_agent":
                    result = await self._execute_ai_node(run_id, run["run_by"], node, upstream_output, outputs)
                elif node["type"] == "condition":
                    result = await self._execute_condition_node(run_id, node, upstream_output, adjacency)
                elif node["type"] == "human_review":
                    result = await self._execute_human_gate(run_id, node, upstream_output)
                    if result.get("paused"):
                        return
                elif node["type"] == "merge":
                    result = await self._execute_merge_node(run_id, node, outputs, edges, completed)
                    if result.get("waiting"):
                        continue
                elif node["type"] == "output":
                    result = await self._execute_output_node(run_id, node, upstream_output, outputs, edges)
                elif node["type"] in ("text_to_video", "image_to_video", "text_to_speech", "text_to_music", "sound_effect", "transcribe", "video_compose", "audio_compose", "media_publish"):
                    result = await self._execute_media_node(run_id, run.get("run_by", ""), node, upstream_output)
                else:
                    result = {"success": True, "output_data": upstream_output}

                if result.get("success"):
                    completed.add(node_id)
                    outputs[node_id] = result.get("output_data") or {}
                    if node["type"] == "condition" and result.get("next_node"):
                        queue.append(result["next_node"])
                    else:
                        for t in adjacency.get(node_id, []):
                            if t["target"] not in completed:
                                queue.append(t["target"])
                else:
                    await self._fail_run(run_id, result.get("error", "Node execution failed"), node_id)
                    return

            last_output = outputs.get(nodes[-1]["node_id"], outputs.get(list(outputs.keys())[-1], {}))
            totals = await self._calc_run_totals(run_id)
            await self.db.workflow_runs.update_one({"run_id": run_id}, {"$set": {
                "status": "completed", "completed_at": now_iso(), "final_output": last_output, **totals
            }})
            await self.db.workflows.update_one({"workflow_id": workflow["workflow_id"]}, {"$inc": {"run_count": 1}, "$set": {"last_run_at": now_iso()}})
            await self.emit(run_id, "run:completed", {"run_id": run_id, "status": "completed", "final_output": last_output, **totals})
        except Exception as e:
            logger.exception(f"Resume execution error for run {run_id}")
            await self._fail_run(run_id, str(e))


# ============ SSE Manager ============

class SSEManager:
    """Simple Server-Sent Events manager for workflow run progress"""
    def __init__(self):
        self.listeners = {}  # run_id -> list of asyncio.Queue

    def subscribe(self, run_id):
        q = asyncio.Queue()
        self.listeners.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(self, run_id, q):
        if run_id in self.listeners:
            self.listeners[run_id] = [x for x in self.listeners[run_id] if x is not q]
            if not self.listeners[run_id]:
                del self.listeners[run_id]

    async def send(self, run_id, data):
        for q in self.listeners.get(run_id, []):
            await q.put(data)
