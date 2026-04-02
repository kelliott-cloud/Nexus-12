"""Direct AI provider API calls for user-provided API keys"""
import os
import uuid
import httpx
from pathlib import Path
from dotenv import load_dotenv
from http_pool import get_http_client
import asyncio
import logging
from data_guard import DataGuard

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

# Per-provider throttle: tracks last call timestamp to avoid hammering rate-limited APIs
import time as _time
_provider_last_call = {}
# Light throttle — just prevent simultaneous duplicate calls, not aggressive rate limit avoidance
_PROVIDER_MIN_INTERVAL = {
    "mistral": 1.0,
    "cohere": 1.0,
    "groq": 0.3,
    "perplexity": 1.0,
    "pi": 1.0,
    "mercury": 2.0,
    "deepseek": 0.5,
    "grok": 1.0,
    "manus": 3.0,
    "qwen": 0.5,
    "kimi": 1.0,
    "llama": 0.3,
    "glm": 1.0,
    "cursor": 1.0,
    "notebooklm": 1.0,
    "copilot": 1.0,
}

async def _throttle_provider(provider_key):
    """Brief pause between calls to same provider to avoid burst."""
    min_interval = _PROVIDER_MIN_INTERVAL.get(provider_key, 0)
    if min_interval <= 0:
        return
    last = _provider_last_call.get(provider_key, 0)
    elapsed = _time.time() - last
    if elapsed < min_interval:
        await asyncio.sleep(min_interval - elapsed)
    _provider_last_call[provider_key] = _time.time()


async def _retry_request(request_fn, max_retries=5, provider_key=None):
    """Retry with fast backoff. Rate limits (429) get 3 quick retries then fail gracefully."""
    import random
    # Rate-limited providers get fewer retries with shorter waits — fail fast, try next round
    rate_limit_retries = 3
    if provider_key:
        await _throttle_provider(provider_key)
    for attempt in range(max_retries):
        try:
            return await request_fn()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                if attempt >= rate_limit_retries - 1:
                    # Don't keep retrying rate limits — fail fast so other agents aren't blocked
                    raise Exception(f"RATE_LIMITED:{provider_key}")
                retry_after = e.response.headers.get("retry-after")
                try:
                    wait = min(float(retry_after), 30)
                except (TypeError, ValueError):
                    wait = min((attempt + 1) * 3.0, 15)
                jitter = random.uniform(0.5, 1.5)
                logger.info(f"Rate limited by {provider_key}. Waiting {wait*jitter:.0f}s (attempt {attempt+1}/{rate_limit_retries})")
                await asyncio.sleep(wait * jitter)
                continue
            elif e.response.status_code >= 500 and attempt < max_retries - 1:
                await asyncio.sleep(2.0 * (attempt + 1) + random.uniform(0, 1))
                continue
            error_msg = str(e)[:200]
            try:
                body = e.response.json()
                if "error" in body:
                    err = body["error"]
                    error_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                elif "message" in body:
                    error_msg = body["message"]
                elif "detail" in body:
                    error_msg = body["detail"]
            except Exception:
                # Response body not JSON — use raw text
                try:
                    error_msg = e.response.text[:200] or str(e)[:200]
                except Exception as _e:
                    import logging; logging.getLogger("ai_providers").warning(f"Suppressed: {_e}")
            if not error_msg or error_msg.strip() == "":
                error_msg = f"HTTP {e.response.status_code} from {provider_key or 'provider'} (empty response body)"
            if e.response.status_code == 429:
                raise Exception(f"RATE_LIMITED:{provider_key}")
            if e.response.status_code == 402:
                raise Exception(f"RATE_LIMITED:{provider_key}")  # Treat credit exhaustion same as rate limit — skip silently
            raise Exception(f"API error ({e.response.status_code}): {error_msg}")
    raise Exception("Max retries exceeded")

PROVIDER_CONFIG = {
    "claude": {
        "base_url": "https://api.anthropic.com/v1/messages",
        "gw_provider": "anthropic",
        "default_model": "claude-opus-4-20250514",
        "type": "anthropic",
    },
    "chatgpt": {
        "base_url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-5.4",
        "type": "openai_compatible",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "type": "openai_compatible",
    },
    "grok": {
        "base_url": "https://api.x.ai/v1/chat/completions",
        "default_model": "grok-3",
        "type": "openai_compatible",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "default_model": "gemini-2.5-pro",
        "type": "gemini",
    },
    "perplexity": {
        "base_url": "https://api.perplexity.ai/chat/completions",
        "default_model": "sonar-pro",
        "type": "openai_compatible",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1/chat/completions",
        "default_model": "mistral-large-latest",
        "type": "openai_compatible",
    },
    "cohere": {
        "base_url": "https://api.cohere.com/v2/chat",
        "default_model": "command-a-03-2025",
        "type": "cohere",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "llama-3.3-70b-versatile",
        "type": "openai_compatible",
    },
    "mercury": {
        "base_url": "https://api.inceptionlabs.ai/v1/chat/completions",
        "default_model": "mercury-2",
        "type": "openai_compatible",
    },
    "pi": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "inflection/inflection-3-pi",
        "type": "openai_compatible",
    },
    "manus": {
        "base_url": "https://api.manus.ai",
        "default_model": "manus-1",
        "type": "manus",
    },
    "qwen": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        "default_model": "qwen-plus",
        "type": "openai_compatible",
    },
    "kimi": {
        "base_url": "https://platform.moonshot.ai/v1/chat/completions",
        "default_model": "kimi-k2.5",
        "type": "openai_compatible",
    },
    "llama": {
        "base_url": "https://api.together.xyz/v1/chat/completions",
        "default_model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "type": "openai_compatible",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "default_model": "glm-4-plus",
        "type": "openai_compatible",
    },
    "cursor": {
        "base_url": "https://api.cursor.com/v1/chat/completions",
        "gw_provider": "openai",
        "default_model": "cursor/composer",
        "type": "openai_compatible",
    },
    "notebooklm": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "google/gemini-2.5-pro-preview",
        "type": "openai_compatible",
    },
    "copilot": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "openai/gpt-4o",
        "type": "openai_compatible",
    },
    "gemma": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "default_model": "gemma-3-27b-it",
        "type": "gemini",
    },
}


# Emergent universal key support removed (NX-005)


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc or "").lower()
    auth_markers = [
        "api error (401)",
        "incorrect api key",
        "invalid x-api-key",
        "authentication",
        "unauthorized",
        "invalid api key",
        "permission denied",
    ]
    return any(marker in msg for marker in auth_markers)






async def call_anthropic(api_key: str, system_prompt: str, user_message: str, model: str = None, workspace_id: str = None) -> str:
    cfg = PROVIDER_CONFIG["claude"]
    model = model or cfg["default_model"]
    no_train = DataGuard.get_no_train_headers("anthropic", workspace_id)

    async def _do():
        client = get_http_client()
        truncated_system = system_prompt[:12000] if len(system_prompt) > 12000 else system_prompt
        truncated_user = user_message[:8000] if len(user_message) > 8000 else user_message
        response = await client.post(
            cfg["base_url"],
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                **no_train,
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "system": truncated_system,
                "messages": [{"role": "user", "content": truncated_user}],
            },
        )
        if response.status_code == 400:
            error_body = response.text
            # Billing/credit errors — don't retry, surface clearly
            if "credit" in error_body.lower() or "billing" in error_body.lower() or "balance" in error_body.lower():
                raise Exception("Anthropic API billing issue. Please check your API key's credit balance at console.anthropic.com")
            logger.error(f"Claude 400 error: {error_body[:300]}")
            # Content too long — try with shorter prompt
            if len(system_prompt) > 4000:
                short_system = system_prompt[:4000]
                retry_resp = await client.post(
                    cfg["base_url"],
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": model, "max_tokens": 4096, "system": short_system, "messages": [{"role": "user", "content": truncated_user}]},
                )
                retry_resp.raise_for_status()
                return retry_resp.json()["content"][0]["text"]
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]
    return await _retry_request(_do, provider_key="anthropic")


async def call_openai_compatible(api_key: str, base_url: str, system_prompt: str, user_message: str, model: str, workspace_id: str = None, provider_key: str = None) -> str:
    async def _do():
        client = get_http_client()
        truncated_system = system_prompt[:12000] if len(system_prompt) > 12000 else system_prompt
        truncated_user = user_message[:8000] if len(user_message) > 8000 else user_message
        # Derive provider for DataGuard from base_url
        provider_name = "mistral" if "mistral.ai" in base_url else "openai" if "openai.com" in base_url else "other"
        no_train = DataGuard.get_no_train_headers(provider_name, workspace_id)
        # Determine max_tokens based on provider
        is_openrouter = "openrouter.ai" in base_url
        is_new_openai = provider_key == "chatgpt" and any(m in model for m in ["gpt-5", "gpt-4.1", "o3", "o1"])
        token_param = "max_completion_tokens" if is_new_openai else "max_tokens"
        if is_openrouter:
            token_limit = 512 if provider_key == "pi" else 4096
        elif provider_key in ("mistral", "perplexity"):
            token_limit = 4096
        else:
            token_limit = 8192
            
        # Build headers — only standard ones for Mistral (rejects custom headers with 400)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider_name != "mistral":
            headers.update(no_train)
        if is_openrouter:
            headers["HTTP-Referer"] = "https://nexus-platform.ai"
            headers["X-Title"] = "Nexus"
            
        response = await client.post(
            base_url,
            headers=headers,
            json={
                "model": model,
                token_param: token_limit,
                "messages": [
                    {"role": "system", "content": truncated_system},
                    {"role": "user", "content": truncated_user},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    return await _retry_request(_do, provider_key=provider_key or "openai")


async def call_gemini(api_key: str, system_prompt: str, user_message: str, model: str = None) -> str:
    """Call Google Gemini API directly"""
    cfg = PROVIDER_CONFIG["gemini"]
    model = model or cfg["default_model"]
    url = f"{cfg['base_url']}/{model}:generateContent"

    async def _do():
        client = get_http_client()
        truncated_system = system_prompt[:12000] if len(system_prompt) > 12000 else system_prompt
        truncated_user = user_message[:8000] if len(user_message) > 8000 else user_message
        response = await client.post(
            url,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={
                "systemInstruction": {"parts": [{"text": truncated_system}]},
                "contents": [{"parts": [{"text": truncated_user}]}],
                "generationConfig": {"maxOutputTokens": 2048},
            },
        )
        response.raise_for_status()
        data = response.json()
        # Safely parse Gemini response — handle missing parts, safety blocks, etc.
        candidates = data.get("candidates") or []
        if not candidates:
            # Check for prompt feedback (safety block)
            feedback = data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "")
            if block_reason:
                return f"_[Response blocked by Gemini safety filter: {block_reason}]_"
            return "_[Gemini returned no candidates]_"
        candidate = candidates[0]
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "SAFETY":
                return "_[Response blocked by Gemini safety filter]_"
            return "_[Gemini returned empty response]_"
        return parts[0].get("text", "")
    return await _retry_request(_do, provider_key="gemini")


async def call_cohere(api_key: str, system_prompt: str, user_message: str, model: str = None) -> str:
    """Call Cohere API v2"""
    cfg = PROVIDER_CONFIG["cohere"]
    model = model or cfg["default_model"]
    # Redirect deprecated models to current equivalents
    COHERE_MODEL_REDIRECTS = {
        "command-r": "command-a-03-2025",
        "command-r-plus": "command-a-03-2025",
        "command": "command-a-03-2025",
        "command-light": "command-a-03-2025",
        "command-nightly": "command-a-03-2025",
        "command-r-08-2024": "command-a-03-2025",
        "command-r-plus-08-2024": "command-a-03-2025",
    }
    if model in COHERE_MODEL_REDIRECTS:
        logger.info(f"Cohere model redirect: {model} → {COHERE_MODEL_REDIRECTS[model]}")
        model = COHERE_MODEL_REDIRECTS[model]

    async def _do():
        client = get_http_client()
        truncated_system = system_prompt[:12000] if len(system_prompt) > 12000 else system_prompt
        truncated_user = user_message[:8000] if len(user_message) > 8000 else user_message
        response = await client.post(
            cfg["base_url"],
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Client-Name": "nexus-platform",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": truncated_system},
                    {"role": "user", "content": truncated_user},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        # v2 response: data.message.content[0].text
        msg = data.get("message") or {}
        content = msg.get("content") or []
        if isinstance(content, list) and len(content) > 0:
            text = content[0].get("text", "")
            if text:
                return text
        if isinstance(content, str) and content:
            return content
        # Fallback: try other response shapes
        if data.get("text"):
            return data["text"]
        if data.get("generations"):
            return data["generations"][0].get("text", "")
        # If we get here, the response structure is unexpected
        logger.warning(f"Cohere unexpected response shape: {list(data.keys())}")
        return "_[Cohere returned unexpected response format]_"
    return await _retry_request(_do, provider_key="cohere")


async def call_manus(api_key: str, system_prompt: str, user_message: str, model: str = None) -> str:
    """Call Manus AI via their task-based API. Submit task, poll for completion."""
    async def _do():
        client = get_http_client()
        truncated_system = system_prompt[:12000] if len(system_prompt) > 12000 else system_prompt
        truncated_user = user_message[:8000] if len(user_message) > 8000 else user_message
            
        # Create a task
        create_resp = await client.post(
            "https://api.manus.ai/v1/tasks",
            headers={"API_KEY": api_key, "Content-Type": "application/json"},
            json={
                "prompt": f"{truncated_system}\n\n---\n\n{truncated_user}",
                "model": model or "manus-1",
            },
        )
        create_resp.raise_for_status()
        task_data = create_resp.json()
        task_id = task_data.get("id") or task_data.get("task_id", "")
            
        if not task_id:
            # Direct response mode
            return (task_data.get("result") or {}).get("text", "") or task_data.get("output", "") or str(task_data)
            
        # Poll for completion (max 60 seconds)
        import asyncio
        for _ in range(30):
            await asyncio.sleep(2)
            status_resp = await client.get(
                f"https://api.manus.ai/v1/tasks/{task_id}",
                headers={"API_KEY": api_key},
            )
            if status_resp.status_code != 200:
                continue
            task = status_resp.json()
            status = task.get("status", "")
            if status in ("completed", "done", "finished"):
                return (task.get("result") or {}).get("text", "") or task.get("output", "") or task.get("response", "")
            elif status in ("failed", "error"):
                return f"_[Manus task failed: {task.get('error', 'Unknown error')}]_"
            
        return "_[Manus task timed out after 60 seconds]_"
    return await _retry_request(_do, provider_key="manus")


async def call_ai_direct(agent_key: str, api_key: str, system_prompt: str, user_message: str, model_override: str = None, workspace_id: str = None, db=None, channel_id: str = None, allow_emergent_fallback: bool = True) -> str:
    """Call an AI model directly using the user's API key"""
    cfg = PROVIDER_CONFIG.get(agent_key)
    if not cfg:
        raise ValueError(f"Unknown agent: {agent_key}")

    model = model_override or cfg["default_model"]
    
    # DataGuard: sanitize content before sending to AI provider
    sanitized_system = DataGuard.sanitize_for_ai(system_prompt, workspace_id)
    sanitized_user = DataGuard.sanitize_for_ai(user_message, workspace_id)
    
    total_chars = len(sanitized_system) + len(sanitized_user)
    logger.info(f"call_ai_direct: {agent_key} model={model} chars={total_chars} [DataGuard active]")
    
    # DataGuard: audit log the transmission
    if db is not None:
        await DataGuard.log_transmission(db, workspace_id or "", agent_key, cfg.get("type", "unknown"), total_chars, channel_id)

    if not api_key:
        raise ValueError(f"No API key provided for {agent_key}. Configure in Settings > AI Keys.")

    # Cloudflare AI Gateway: route through gateway if configured
    effective_base_url = cfg.get("base_url", "")
    cf_account = os.environ.get("CF_ACCOUNT_ID", "")
    cf_gw_name = os.environ.get("CF_AI_GATEWAY_NAME", "nexus-gw")
    if cf_account and cfg.get("gw_provider"):
        gw_base = f"https://gateway.ai.cloudflare.com/v1/{cf_account}/{cf_gw_name}/{cfg['gw_provider']}"
        # For OpenAI-compatible, append the path suffix
        if cfg["type"] == "anthropic":
            effective_base_url = f"{gw_base}/v1/messages"
        elif cfg["type"] == "gemini":
            effective_base_url = f"{gw_base}/v1/models"
        elif cfg["type"] == "cohere":
            effective_base_url = f"{gw_base}/v2/chat"
        else:
            effective_base_url = f"{gw_base}/v1/chat/completions"
        logger.debug(f"AI Gateway routing: {agent_key} -> {effective_base_url[:60]}")

    from keystone import circuit_breaker

    async def _ai_call():
        if cfg["type"] == "anthropic":
            return await call_anthropic(api_key, sanitized_system, sanitized_user, model, workspace_id)
        elif cfg["type"] == "gemini":
            return await call_gemini(api_key, sanitized_system, sanitized_user, model)
        elif cfg["type"] == "cohere":
            return await call_cohere(api_key, sanitized_system, sanitized_user, model)
        elif cfg["type"] == "manus":
            return await call_manus(api_key, sanitized_system, sanitized_user, model)
        else:
            return await call_openai_compatible(
                api_key, effective_base_url, sanitized_system, sanitized_user, model, workspace_id, provider_key=agent_key
            )

    try:
        return await circuit_breaker.call_with_breaker(agent_key, _ai_call)
    except Exception as exc:
        raise


async def test_api_key(agent_key: str, api_key: str) -> dict:
    """Test if an API key is valid by making a minimal API call"""
    cfg = PROVIDER_CONFIG.get(agent_key)
    if not cfg:
        return {"success": False, "error": f"Unknown agent: {agent_key}"}
    
    test_prompt = "Say 'OK' and nothing else."
    system_prompt = "You are a helpful assistant. Keep your response extremely brief."
    
    debug_info = {
        "agent": agent_key,
        "model": cfg["default_model"],
        "endpoint": cfg["base_url"],
        "timestamp": None,
        "request_headers": None,
        "response_status": None,
        "response_headers": None,
        "response_body": None,
        "error_type": None,
        "error_message": None,
    }
    
    import time
    debug_info["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    
    try:
        response = await call_ai_direct(agent_key, api_key, system_prompt, test_prompt, allow_emergent_fallback=False)
        debug_info["response_status"] = 200
        debug_info["response_body"] = f"Success - Response preview: {response[:100]}..." if response else "Empty response"
        return {
            "success": True,
            "message": "API key is valid",
            "model": cfg["default_model"],
            "response_preview": response[:50] if response else None,
        }
    except httpx.HTTPStatusError as e:
        error_msg = "Invalid API key or authentication failed"
        debug_info["response_status"] = e.response.status_code
        debug_info["error_type"] = "HTTPStatusError"
        
        # Try to get response body for detailed error
        try:
            response_text = e.response.text
            debug_info["response_body"] = response_text[:1000] if response_text else "No response body"
            # Try to parse JSON error
            try:
                import json
                error_json = json.loads(response_text)
                if "error" in error_json:
                    if isinstance(error_json["error"], dict):
                        error_msg = error_json["error"].get("message", error_msg)
                    else:
                        error_msg = str(error_json["error"])
                elif "message" in error_json:
                    error_msg = error_json["message"]
            except Exception as _e:
                import logging; logging.getLogger("ai_providers").warning(f"Suppressed: {_e}")
        except Exception:
            debug_info["response_body"] = "Could not read response body"
        
        # Get response headers
        try:
            debug_info["response_headers"] = dict(e.response.headers)
        except Exception as _e:
            import logging; logging.getLogger("ai_providers").warning(f"Suppressed: {_e}")
            
        debug_info["error_message"] = error_msg
        
        if e.response.status_code == 401:
            error_msg = f"Invalid API key: {error_msg}"
        elif e.response.status_code == 403:
            error_msg = f"Permission denied: {error_msg}"
        elif e.response.status_code == 429:
            error_msg = "Rate limit exceeded - but key is valid"
            return {"success": True, "message": error_msg, "model": cfg["default_model"]}
        elif e.response.status_code == 400:
            error_msg = f"Bad request: {error_msg}"
        elif e.response.status_code == 404:
            error_msg = f"Model not found: {error_msg}"
            
        return {"success": False, "error": error_msg, "status_code": e.response.status_code}
    except httpx.ConnectError as e:
        debug_info["error_type"] = "ConnectError"
        debug_info["error_message"] = str(e)
        return {"success": False, "error": f"Connection failed: {str(e)}"}
    except httpx.TimeoutException as e:
        debug_info["error_type"] = "TimeoutException"
        debug_info["error_message"] = str(e)
        return {"success": False, "error": "Request timed out"}
    except Exception as e:
        debug_info["error_type"] = type(e).__name__
        debug_info["error_message"] = str(e)
        return {"success": False, "error": str(e)}


# ============================================================
# Google AI Ecosystem — Imagen 4, Nano Banana, Veo 3.1, Lyria 3
# ============================================================

async def call_imagen4(api_key: str, prompt: str, model: str = "imagen-4.0-generate-001",
                        aspect_ratio: str = "1:1", num_images: int = 1,
                        negative_prompt: str = "", workspace_id: str = None) -> dict:
    """Generate images using Imagen 4 via Gemini API /predict endpoint."""
    from data_guard import DataGuard
    sanitized = DataGuard.sanitize_for_ai(prompt, workspace_id)
    import httpx
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateImages",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "prompt": sanitized,
                "config": {
                    "numberOfImages": min(num_images, 4),
                    "aspectRatio": aspect_ratio,
                    "negativePrompt": negative_prompt,
                    "personGeneration": "ALLOW_ADULT",
                    "outputOptions": {"addWatermark": True},
                }
            })
        if resp.status_code != 200:
            raise Exception(f"Imagen 4 error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        images = []
        for img in data.get("generatedImages", data.get("predictions", [])):
            if isinstance(img, dict):
                b64 = img.get("image", {}).get("imageBytes", "") or img.get("bytesBase64Encoded", "")
                mime = img.get("image", {}).get("mimeType", "image/png") or img.get("mimeType", "image/png")
                images.append({"base64": b64, "mime_type": mime})
        return {"images": images, "model": model}


async def call_nano_banana(api_key: str, prompt: str, input_image_b64: str = None,
                            model: str = "gemini-3.1-flash-image-preview",
                            workspace_id: str = None) -> dict:
    """Generate or edit images using Nano Banana (Gemini Native Image)."""
    from data_guard import DataGuard
    sanitized = DataGuard.sanitize_for_ai(prompt, workspace_id)
    import httpx
    contents = [{"parts": [{"text": sanitized}]}]
    if input_image_b64:
        contents[0]["parts"].insert(0, {"inline_data": {"mime_type": "image/png", "data": input_image_b64}})
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={"contents": contents, "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}})
        if resp.status_code != 200:
            raise Exception(f"Nano Banana error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        images, text_parts = [], []
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    images.append({"base64": part["inlineData"]["data"], "mime_type": part["inlineData"]["mimeType"]})
                elif "text" in part:
                    text_parts.append(part["text"])
        return {"images": images, "text": "\n".join(text_parts), "model": model}


async def call_veo(api_key: str, prompt: str, model: str = "veo-3.1-generate-preview",
                    resolution: str = "720p", aspect_ratio: str = "16:9",
                    input_image_b64: str = None, workspace_id: str = None) -> dict:
    """Generate video using Veo 3.1. Returns operation for polling."""
    from data_guard import DataGuard
    sanitized = DataGuard.sanitize_for_ai(prompt, workspace_id)
    import httpx
    payload = {
        "model": f"models/{model}", "prompt": sanitized,
        "config": {"aspectRatio": aspect_ratio, "resolution": resolution,
                   "numberOfVideos": 1, "durationSeconds": 8,
                   "personGeneration": "allow_adult", "generateAudio": True}
    }
    if input_image_b64:
        payload["image"] = {"imageBytes": input_image_b64, "mimeType": "image/png"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateVideos",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload)
        if resp.status_code != 200:
            raise Exception(f"Veo error {resp.status_code}: {resp.text[:500]}")
        operation = resp.json()
        return {"operation_name": operation.get("name", ""), "status": "pending"}


async def poll_veo_operation(api_key: str, operation_name: str) -> dict:
    """Poll a Veo operation until complete."""
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/{operation_name}",
            headers={"x-goog-api-key": api_key})
        data = resp.json()
        if data.get("done"):
            videos = [{"uri": v.get("video", {}).get("uri", "")}
                      for v in data.get("response", {}).get("generatedVideos", [])]
            return {"status": "completed", "videos": videos}
        return {"status": "pending", "metadata": data.get("metadata", {})}


async def call_lyria(api_key: str, prompt: str, model: str = "lyria-3-clip-preview",
                      workspace_id: str = None) -> dict:
    """Generate music using Lyria 3 via Gemini API generateContent."""
    from data_guard import DataGuard
    sanitized = DataGuard.sanitize_for_ai(prompt, workspace_id)
    import httpx
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": sanitized}]}],
                  "generationConfig": {"responseModalities": ["AUDIO", "TEXT"]}})
        if resp.status_code != 200:
            raise Exception(f"Lyria error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        audio_parts, lyrics = [], []
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    audio_parts.append({"base64": part["inlineData"]["data"],
                                        "mime_type": part["inlineData"].get("mimeType", "audio/wav")})
                elif "text" in part:
                    lyrics.append(part["text"])
        return {"audio": audio_parts, "lyrics": "\n".join(lyrics), "model": model}
