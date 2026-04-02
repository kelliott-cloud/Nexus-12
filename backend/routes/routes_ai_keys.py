"""API key management routes - account-level and workspace-level"""
import os
import logging
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import HTTPException, Request
from typing import Optional, Dict
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Initialize encryption - auto-generate if not provided
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', '')
if not ENCRYPTION_KEY:
    if os.environ.get('ENVIRONMENT', 'development') == 'production':
        raise RuntimeError("ENCRYPTION_KEY must be set in production. Previously encrypted keys will be unrecoverable without it.")
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    _env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    try:
        with open(_env_path, 'a') as _f:
            _f.write(f"\nENCRYPTION_KEY={ENCRYPTION_KEY}\n")
        logger.warning("ENCRYPTION_KEY not set — generated and saved to .env")
    except Exception as _write_err:
        logger.error(f"Generated TEMPORARY key (could not write .env: {_write_err})")

try:
    fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
    logger.info("Encryption initialized successfully")
except Exception as e:
    raise RuntimeError(f"FATAL: Failed to init encryption: {e}. Restore original ENCRYPTION_KEY or clear encrypted keys from DB.")

# All supported AI agents
ALL_AGENTS = [
    "claude", "chatgpt", "deepseek", "grok", "gemini", "perplexity",
    "mistral", "cohere", "groq", "mercury", "pi", "manus", "qwen",
    "kimi", "llama", "glm", "cursor", "notebooklm", "copilot",
]


def encrypt_key(api_key: str) -> str:
    try:
        return fernet.encrypt(api_key.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise HTTPException(500, "Failed to encrypt API key. Check server encryption configuration.")


def decrypt_key(encrypted: str) -> str:
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise RuntimeError(f"Failed to decrypt key: {e}")


def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "****"
    return key[:4] + "..." + key[-4:]


class SaveAIKeys(BaseModel):
    claude: Optional[str] = None
    chatgpt: Optional[str] = None
    deepseek: Optional[str] = None
    grok: Optional[str] = None
    gemini: Optional[str] = None
    perplexity: Optional[str] = None
    mistral: Optional[str] = None
    cohere: Optional[str] = None
    groq: Optional[str] = None
    mercury: Optional[str] = None
    pi: Optional[str] = None
    manus: Optional[str] = None
    qwen: Optional[str] = None
    kimi: Optional[str] = None
    llama: Optional[str] = None
    glm: Optional[str] = None
    cursor: Optional[str] = None
    notebooklm: Optional[str] = None
    copilot: Optional[str] = None


class WorkspaceAIConfig(BaseModel):
    claude: Optional[Dict] = None
    chatgpt: Optional[Dict] = None
    deepseek: Optional[Dict] = None
    grok: Optional[Dict] = None
    gemini: Optional[Dict] = None
    perplexity: Optional[Dict] = None
    mistral: Optional[Dict] = None
    cohere: Optional[Dict] = None
    groq: Optional[Dict] = None
    mercury: Optional[Dict] = None
    pi: Optional[Dict] = None


class TestKeyRequest(BaseModel):
    agent: str
    api_key: str


def register_ai_key_routes(api_router, db, get_current_user):
    @api_router.get("/settings/ai-keys")
    async def get_ai_keys(request: Request):
        user = await get_current_user(request)
        ai_keys = user.get("ai_keys") or {}

        # Return masked keys + connection status
        result = {}
        for agent in ALL_AGENTS:
            encrypted = ai_keys.get(agent)
            if encrypted:
                try:
                    decrypted = decrypt_key(encrypted)
                    result[agent] = {
                        "configured": True,
                        "masked_key": mask_key(decrypted),
                    }
                except Exception as e:
                    logger.warning(f"Failed to decrypt key for {agent}: {e}")
                    result[agent] = {"configured": False, "masked_key": None, "error": "Key decryption failed - may need to re-enter"}
            else:
                result[agent] = {"configured": False, "masked_key": None}

        return result

    @api_router.post("/settings/ai-keys")
    async def save_ai_keys(data: SaveAIKeys, request: Request):
        user = await get_current_user(request)
        ai_keys = user.get("ai_keys") or {}

        for agent in ALL_AGENTS:
            key_value = getattr(data, agent, None)
            if key_value is not None:
                if key_value == "":
                    ai_keys.pop(agent, None)
                else:
                    ai_keys[agent] = encrypt_key(key_value)

        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"ai_keys": ai_keys, "ai_keys_updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        # Clear key resolver cache so new keys take effect immediately
        from key_resolver import clear_cache
        clear_cache()

        # Return updated status
        result = {}
        for agent in ALL_AGENTS:
            encrypted = ai_keys.get(agent)
            if encrypted:
                try:
                    result[agent] = {"configured": True, "masked_key": mask_key(decrypt_key(encrypted))}
                except Exception as e:
                    logger.warning(f"Failed to decrypt key for {agent} after save: {e}")
                    result[agent] = {"configured": True, "masked_key": "****", "error": "Saved but decryption verify failed"}
            else:
                result[agent] = {"configured": False, "masked_key": None}

        return result

    @api_router.delete("/settings/ai-keys/{agent}")
    async def delete_ai_key(agent: str, request: Request):
        user = await get_current_user(request)
        if agent not in ALL_AGENTS:
            raise HTTPException(400, "Invalid agent")

        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$unset": {f"ai_keys.{agent}": ""}}
        )
        from key_resolver import clear_cache
        clear_cache()
        return {"message": f"{agent} key removed"}

    @api_router.post("/settings/ai-keys/test")
    async def test_ai_key(data: TestKeyRequest, request: Request):
        """Test if an API key is valid by making a minimal API call"""
        await get_current_user(request)
        
        if data.agent not in ALL_AGENTS:
            raise HTTPException(400, "Invalid agent")
        
        from ai_providers import test_api_key
        result = await test_api_key(data.agent, data.api_key)
        return result

    @api_router.post("/settings/ai-keys/test-all")
    async def test_all_ai_keys(request: Request):
        """Test all configured API keys at once"""
        import asyncio
        from ai_providers import test_api_key
        
        user = await get_current_user(request)
        ai_keys = user.get("ai_keys") or {}
        
        results = {}
        tasks = []
        agents_to_test = []
        
        for agent in ALL_AGENTS:
            encrypted = ai_keys.get(agent)
            if encrypted:
                try:
                    decrypted = decrypt_key(encrypted)
                    agents_to_test.append(agent)
                    tasks.append(test_api_key(agent, decrypted))
                except Exception as _e:
                    logger.warning(f"Caught exception: {_e}")
                    results[agent] = {"success": False, "error": "Failed to decrypt key", "tested": True}
            else:
                results[agent] = {"success": None, "error": None, "tested": False, "message": "No key configured"}
        
        # Run all tests concurrently
        if tasks:
            test_results = await asyncio.gather(*tasks, return_exceptions=True)
            for agent, result in zip(agents_to_test, test_results):
                if isinstance(result, Exception):
                    results[agent] = {"success": False, "error": str(result), "tested": True}
                else:
                    results[agent] = {**result, "tested": True}
        
        # Summary stats
        tested_count = sum(1 for r in results.values() if r.get("tested"))
        passed_count = sum(1 for r in results.values() if r.get("success") == True)
        failed_count = sum(1 for r in results.values() if r.get("success") == False)
        
        return {
            "results": results,
            "summary": {
                "total_configured": tested_count,
                "passed": passed_count,
                "failed": failed_count
            }
        }

    @api_router.post("/workspaces/{workspace_id}/ai-config")
    async def save_workspace_ai_config(workspace_id: str, data: WorkspaceAIConfig, request: Request):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)

        ai_config = {}
        for agent in ALL_AGENTS:
            config = getattr(data, agent, None)
            if config:
                entry = {
                    "enabled": config.get("enabled", False),
                    "key_source": config.get("key_source", "nexus"),
                }
                project_key = config.get("api_key")
                if project_key and config.get("key_source") == "project":
                    entry["api_key_encrypted"] = encrypt_key(project_key)
                ai_config[agent] = entry

        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"ai_config": ai_config, "ai_config_updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        from key_resolver import clear_cache
        clear_cache()

        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        return ws

    @api_router.get("/workspaces/{workspace_id}/ai-config")
    async def get_workspace_ai_config(workspace_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not ws:
            raise HTTPException(404, "Workspace not found")

        ai_config = ws.get("ai_config") or {}
        user_keys = user.get("ai_keys") or {}

        result = {}
        for agent in ALL_AGENTS:
            cfg = ai_config.get(agent, {})
            has_account_key = agent in user_keys
            has_project_key = bool(cfg.get("api_key_encrypted"))

            result[agent] = {
                "enabled": cfg.get("enabled", False),
                "key_source": cfg.get("key_source", "nexus"),
                "has_account_key": has_account_key,
                "has_project_key": has_project_key,
            }

        return result

    @api_router.get("/settings/ai-keys/health")
    async def ai_keys_health(request: Request):
        """Check if the encryption system is working"""
        await get_current_user(request)
        try:
            test_val = "test_key_12345"
            encrypted = fernet.encrypt(test_val.encode()).decode()
            decrypted = fernet.decrypt(encrypted.encode()).decode()
            ok = decrypted == test_val
            return {
                "encryption_working": ok,
                "key_source": "env" if os.environ.get('ENCRYPTION_KEY') else "auto_generated",
            }
        except Exception as e:
            return {"encryption_working": False, "error": str(e)}
