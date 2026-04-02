from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import asyncio
import time
import httpx
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Add routes directory to path so internal imports within route files work
import sys
if str(ROOT_DIR / "routes") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "routes"))

# Configure structured JSON logging for production
import json as _json_log
import json
import secrets

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return _json_log.dumps(log_entry)

# Use JSON format if STRUCTURED_LOGGING env var is set, otherwise human-readable
if os.environ.get("STRUCTURED_LOGGING"):
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress noisy loggers from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# Emergent integrations removed — using direct provider APIs
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# Startup configuration validator (NX-P0)
def validate_config():
    """Check all required env vars at once and report all missing."""
    required = {
        "MONGO_URL": "MongoDB connection string",
        "DB_NAME": "Database name",
        "ENCRYPTION_KEY": "Fernet key for encrypting API keys",
        "SUPER_ADMIN_EMAIL": "Email for the initial super admin account",
    }
    missing = []
    for var, desc in required.items():
        if not os.environ.get(var, "").strip():
            missing.append(f"  - {var}: {desc}")
    if missing:
        print("\n[FATAL] Missing required environment variables:\n" + "\n".join(missing))
        print("\nSee backend/.env.example for a template.\n")
        raise SystemExit(1)

validate_config()

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
client = AsyncIOMotorClient(mongo_url)
_raw_db = client[db_name]

# Wrap DB to auto-inject instance_id on every insert
from instance_registry import wrap_collection

class InstanceTrackedDB:
    """Thin wrapper around AsyncIOMotorDatabase that auto-injects instance_id."""
    def __init__(self, raw_db):
        object.__setattr__(self, '_raw_db', raw_db)
        object.__setattr__(self, '_cache', {})

    def __getattr__(self, name):
        cache = object.__getattribute__(self, '_cache')
        if name not in cache:
            raw_db = object.__getattribute__(self, '_raw_db')
            cache[name] = wrap_collection(getattr(raw_db, name))
        return cache[name]

    def __getitem__(self, name):
        cache = object.__getattribute__(self, '_cache')
        if name not in cache:
            raw_db = object.__getattribute__(self, '_raw_db')
            cache[name] = wrap_collection(raw_db[name])
        return cache[name]

    async def command(self, *args, **kwargs):
        raw_db = object.__getattribute__(self, '_raw_db')
        return await raw_db.command(*args, **kwargs)

db = InstanceTrackedDB(_raw_db)

# LLM Key
# Platform API keys are resolved from environment: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_AI_KEY

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    """N7-010: Unified startup/shutdown lifecycle (replaces deprecated on_event)."""
    # Startup
    await _validate_redis_on_startup()
    await _create_indexes()
    yield
    # Shutdown
    await _graceful_shutdown()

app = FastAPI(
    title="Nexus Platform API",
    description="AI Collaboration Platform — 19 AI models, Agent Marketplace, enterprise SSO, real-time health monitoring, and comprehensive API documentation.",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "Auth", "description": "Authentication, sessions, MFA"},
        {"name": "SSO", "description": "SAML 2.0 and OIDC enterprise SSO — hardened with session binding, auth_time freshness, acr validation"},
        {"name": "Workspaces", "description": "Workspace CRUD and membership"},
        {"name": "Channels", "description": "Channel management and messaging"},
        {"name": "AI", "description": "AI collaboration, agents, and skills — 19 integrated models"},
        {"name": "Marketplace", "description": "AI Agent Marketplace — discover, rate, share, and install custom agent configurations"},
        {"name": "Projects", "description": "Project and task management"},
        {"name": "Code", "description": "Code repository and execution"},
        {"name": "Wiki", "description": "Wiki pages and documentation"},
        {"name": "Files", "description": "File upload and storage"},
        {"name": "Search", "description": "Global cross-entity search"},
        {"name": "Admin", "description": "Platform administration"},
        {"name": "SCIM", "description": "SCIM 2.0 user provisioning"},
        {"name": "Health", "description": "Health checks, status, Redis health probe, system metrics"},
    ],
)

# CORS — handle credentials correctly across all environments
_cors_origins = os.environ.get('CORS_ORIGINS', '')
if _cors_origins == '*' or not _cors_origins:
    # When wildcard or empty, reflect the request origin dynamically
    # This is required because Access-Control-Allow-Origin: * is rejected
    # by browsers when withCredentials=true (cookies)
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response as StarletteResponse

    # W4b: Proper domain suffix matching (not substring)
    from urllib.parse import urlparse
    _extra_domains = os.environ.get('CORS_ALLOWED_DOMAINS', '').strip()
    ALLOWED_DOMAINS = ['nexus.cloud', 'cloud.nexus', 'localhost', '127.0.0.1']
    if _extra_domains:
        ALLOWED_DOMAINS.extend([d.strip() for d in _extra_domains.split(',') if d.strip()])

    def is_origin_allowed(origin):
        if not origin:
            return False
        try:
            parsed = urlparse(origin)
            hostname = (parsed.hostname or '').lower()
            return any(hostname == d or hostname.endswith('.' + d) for d in ALLOWED_DOMAINS)
        except Exception:
            return False

    class DynamicCORSMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            origin = request.headers.get("origin", "")
            if request.method == "OPTIONS":
                response = StarletteResponse(status_code=204)
            else:
                response = await call_next(request)
            if is_origin_allowed(origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
            # W4c: Don't set Allow-Origin for unknown origins
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Max-Age"] = "300"
            return response

    app.add_middleware(DynamicCORSMiddleware)
    logger.info("CORS: Dynamic origin reflection enabled (credentials-safe)")
else:
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=_cors_origins.split(','),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS: Explicit origins: {_cors_origins}")

# Rate limiter + request size middleware — imported from nexus_middleware.py
from nexus_middleware import rate_limit_and_size_middleware, csrf_middleware, correlation_id_middleware
app.middleware("http")(correlation_id_middleware)
app.middleware("http")(rate_limit_and_size_middleware)
app.middleware("http")(csrf_middleware)

# Module enforcement middleware — blocks routes for disabled modules
from module_middleware import module_enforcement_middleware
async def _module_middleware(request, call_next):
    return await module_enforcement_middleware(request, call_next, db=db)
app.middleware("http")(_module_middleware)

# Tenant isolation middleware — enforces workspace access at middleware layer
from tenant_middleware import tenant_isolation_middleware
async def _tenant_middleware(request, call_next):
    return await tenant_isolation_middleware(request, call_next, db=db)
app.middleware("http")(_tenant_middleware)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://assets.emergent.sh https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https://*.emergentagent.com https://*.emergent.sh wss: https:; "
        "frame-ancestors 'self' https://*.emergentagent.com https://*.emergent.sh; "
        "base-uri 'self'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


api_router = APIRouter(prefix="/api")

# WebSocket connection manager — imported from nexus_websocket.py
from nexus_websocket import ConnectionManager
ws_manager = ConnectionManager()

@app.websocket("/api/ws/channels/{channel_id}")
async def websocket_channel(websocket: WebSocket, channel_id: str):
    """WebSocket endpoint — auth via cookie OR first-message token."""
    await websocket.accept()
    try:
        user_id = None
        # Try cookie auth first (primary path after N7R-004)
        session_token = websocket.cookies.get("session_token", "")
        if session_token:
            session = await _raw_db.user_sessions.find_one(
                {"session_token": session_token},
                {"_id": 0, "user_id": 1, "expires_at": 1}
            )
            if session:
                expires_at = session.get("expires_at", "")
                if isinstance(expires_at, str) and expires_at:
                    expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at and expires_at > datetime.now(timezone.utc):
                    user_id = session["user_id"]

        # Fallback: first message token (bridge handoff / legacy clients)
        if not user_id:
            auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            session = await _raw_db.user_sessions.find_one(
                {"session_token": auth_msg.strip()},
                {"_id": 0, "user_id": 1, "expires_at": 1}
            )
            if not session:
                await websocket.send_json({"type": "error", "message": "Auth failed"})
                await websocket.close(code=4001)
                return
            expires_at = session.get("expires_at", "")
            if isinstance(expires_at, str) and expires_at:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if not expires_at or expires_at < datetime.now(timezone.utc):
                await websocket.send_json({"type": "error", "message": "Session expired"})
                await websocket.close(code=4001)
                return
            user_id = session["user_id"]

        # Auth passed — add to broadcast
        ws_manager.connections.setdefault(channel_id, []).append(websocket)
        await websocket.send_json({"type": "auth_ok", "user_id": user_id})
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        ws_manager.disconnect(channel_id, websocket)

# Health check with DB connectivity
# Health routes registered via route_registry
# Registered after get_current_user is defined (line ~340)

# Redis startup validation
async def _validate_redis_on_startup():
    from redis_client import REDIS_REQUIRED, get_redis
    if REDIS_REQUIRED:
        try:
            r = await get_redis()
            if r:
                logger.info("Redis startup check PASSED (REDIS_REQUIRED=true)")
            else:
                logger.error("Redis startup check FAILED — REDIS_REQUIRED=true but connection unavailable")
        except RuntimeError as e:
            logger.critical(f"Redis startup FATAL: {e}")
            raise
    else:
        logger.info("Redis startup: optional mode (REDIS_REQUIRED not set)")

# Graceful shutdown — handled by unified handler below (see shutdown_db_client)

# Data Guard audit trail
@api_router.get("/admin/data-transmissions")
async def get_data_transmissions(request: Request, limit: int = 50):
    """View audit trail of data sent to AI providers (admin only)"""
    user = await get_current_user(request)
    from routes.routes_admin import is_super_admin
    if not await is_super_admin(db, user["user_id"]):
        raise HTTPException(403, "Admin access required")
    transmissions = await db.data_transmissions.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"transmissions": transmissions}

# Input sanitization helper (using nh3 — Rust-based, secure)
from nexus_utils import sanitize_html

# AI Model configurations — imported from nexus_config.py
from nexus_config import AI_MODELS, CODE_REPO_PROMPT


# Human Priority Queue — pauses agents when human sends a message

# Pydantic models — imported from nexus_models.py
from nexus_models import SessionExchange, WorkspaceCreate, ChannelCreate, MessageCreate, CheckoutRequest, WorkspaceUpdate, ChannelUpdate

# ============ Auth Helpers ============

async def get_current_user(request: Request):
    """Validate session — delegates to nexus_auth module."""
    from nexus_auth import get_current_user_impl
    return await get_current_user_impl(db, request)

# Early route registrations now handled by route_registry (called below)

# ============ AI Collaboration ============
# Shared state imported from collaboration_engine module
from state import state_get, state_set, state_delete, state_exists
from collaboration_engine import (
    active_collaborations, persist_sessions, auto_collab_sessions,
    hard_stop as _hard_stop, pending_batch as _pending_batch, human_priority,
    get_collaboration_status as _get_collab_status,
)

from collaboration_core import get_ai_key_for_agent, run_ai_collaboration, run_persist_collaboration, init_collaboration_core
init_collaboration_core(db, ws_manager)

# Shared state for active task sessions
active_task_sessions: dict = {}

async def run_task_session_agent(session_id: str, user_id: str, workspace_id: str):
    """Run AI agent for a task session"""
    try:
        from ai_providers import call_ai_direct

        session = await db.task_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            return
        
        agent_info = session["agent"]
        base_model_key = agent_info["base_model"]
        
        if base_model_key not in AI_MODELS:
            return
        
        base_model_config = AI_MODELS[base_model_key]
        
        # Build system prompt
        if agent_info["is_nexus_agent"]:
            nexus_agent = await db.nexus_agents.find_one({"agent_id": agent_info["agent_id"]}, {"_id": 0})
            system_prompt = nexus_agent["system_prompt"] if nexus_agent else base_model_config["system_prompt"]
        else:
            system_prompt = base_model_config["system_prompt"]
        
        # Get conversation history
        messages = await db.task_session_messages.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        
        context = f"Task: {session['title']}\n"
        if session.get("description"):
            context += f"Description: {session['description']}\n"
        context += "\n=== CONVERSATION ===\n"
        for msg in messages:
            sender = msg.get("sender_name", "Unknown")
            context += f"[{sender}]: {msg['content']}\n\n"
        context += "=== END CONVERSATION ==="
        
        user_prompt = f"""{context}

Your task: Respond to help complete the task above.
- Stay focused on the task at hand
- When writing code: provide COMPLETE, WORKING files — no placeholders or truncation
- Use markdown code blocks with language tags
- Think through architecture and error handling
- Use repo_write_file tool to save code to the repository
- Be thorough and detail-oriented"""

        active_task_sessions[session_id] = "thinking"
        
        # Get user API key for this model (includes Nexus managed key fallback)
        from managed_keys import init_managed_keys, _db as mk_db
        if mk_db is None:
            init_managed_keys(db)
        user_api_key, key_source = await get_ai_key_for_agent(user_id, workspace_id, base_model_key)
        
        # All models require user API key - no fallback
        if not user_api_key:
            error_msg = {
                "message_id": f"tsm_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "sender_type": "system",
                "sender_id": "system",
                "sender_name": "System",
                "content": f"_{agent_info['name']} requires an API key. Add your {base_model_config['name']} key in Settings._",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.task_session_messages.insert_one(error_msg)
            return
        
        try:
            response_text = await call_ai_direct(
                base_model_key,
                user_api_key,
                system_prompt,
                user_prompt,
                workspace_id=workspace_id, db=db,
            )
            
            # Save AI response
            ai_message = {
                "message_id": f"tsm_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "sender_type": "ai",
                "sender_id": agent_info["agent_id"],
                "sender_name": agent_info["name"],
                "content": response_text,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.task_session_messages.insert_one(ai_message)
            
            # Update session
            await db.task_sessions.update_one(
                {"session_id": session_id},
                {
                    "$inc": {"message_count": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                }
            )
            
            # Send notification
            try:
                from routes.routes_notifications import notify_task_session_response
                await notify_task_session_response(db, session_id, agent_info["name"])
            except Exception as notif_err:
                logger.warning(f"Failed to send notification: {notif_err}")
            
        except Exception as e:
            logger.error(f"Task session agent error: {e}")
            error_msg = {
                "message_id": f"tsm_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "sender_type": "system",
                "sender_id": "system",
                "sender_name": "System",
                "content": f"_Error: {str(e)}_",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.task_session_messages.insert_one(error_msg)
    
    except Exception as e:
        logger.error(f"Task session error: {e}")
    finally:
        active_task_sessions.pop(session_id, None)

@api_router.get("/task-sessions/{session_id}/status")
async def get_task_session_status(session_id: str, request: Request):
    await get_current_user(request)
    is_thinking = active_task_sessions.get(session_id) == "thinking"
    return {"is_thinking": is_thinking}

# ============ Chat Transcript Download ============

@api_router.get("/channels/{channel_id}/transcript")
async def download_channel_transcript(channel_id: str, request: Request):
    """Download full chat history as a ZIP file containing markdown transcript"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    import io
    import zipfile

    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(404, "Channel not found")

    messages = await db.messages.find(
        {"channel_id": channel_id},
        {"_id": 0, "sender_name": 1, "sender_type": 1, "content": 1,
         "created_at": 1, "ai_model": 1, "ai_provider": 1, "model_used": 1, "agent": 1}
    ).sort("created_at", 1).to_list(500)

    if not messages:
        raise HTTPException(404, "No messages in channel")

    # Build markdown transcript
    channel_name = channel.get("name", "channel")
    workspace = await db.workspaces.find_one({"workspace_id": channel.get("workspace_id", "")}, {"_id": 0, "name": 1})
    ws_name = workspace.get("name", "workspace") if workspace else "workspace"

    lines = [
        f"# Chat Transcript: #{channel_name}",
        f"**Workspace:** {ws_name}",
        f"**Channel:** #{channel_name}",
        f"**AI Agents:** {', '.join(channel.get('ai_agents', []))}",
        f"**Messages:** {len(messages)}",
        f"**Exported:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        timestamp = msg.get("created_at", "")
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts = timestamp[:16] if timestamp else ""

        sender = msg.get("sender_name", "Unknown")
        sender_type = msg.get("sender_type", "")
        content = msg.get("content", "")

        if sender_type == "human":
            lines.append(f"### {sender} [{ts}]")
        elif sender_type == "ai":
            model = msg.get("ai_model", "")
            provider = msg.get("ai_provider", "")
            lines.append(f"### {sender} ({model}) [{ts}]")
            if provider:
                lines.append(f"*Provider: {provider}*")
        elif sender_type == "system":
            lines.append(f"**System** [{ts}]")
        elif sender_type == "tool":
            lines.append(f"**Tool Result** ({sender}) [{ts}]")
        else:
            lines.append(f"### {sender} [{ts}]")

        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    transcript_md = "\n".join(lines)

    # Also create a JSON version
    import json
    transcript_json = json.dumps({
        "channel": channel_name,
        "workspace": ws_name,
        "agents": channel.get("ai_agents") or [],
        "message_count": len(messages),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "messages": [{
            "sender": m.get("sender_name"),
            "sender_type": m.get("sender_type"),
            "ai_model": m.get("ai_model"),
            "content": m.get("content"),
            "timestamp": m.get("created_at"),
        } for m in messages],
    }, indent=2, default=str)

    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{channel_name}_transcript.md", transcript_md)
        zf.writestr(f"{channel_name}_transcript.json", transcript_json)
    zip_buffer.seek(0)

    from fastapi.responses import StreamingResponse
    safe_name = channel_name.replace(" ", "_").lower()
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_transcript.zip"'}
    )




@api_router.get("/platform/capabilities")
async def get_platform_capabilities(request: Request):
    """View the current platform capabilities manifest sent to AI agents"""
    await get_current_user(request)
    from platform_capabilities import PLATFORM_CAPABILITIES, PLATFORM_VERSION, TOOL_COUNT
    from nexus_config import FEATURE_FLAGS
    return {
        "version": PLATFORM_VERSION,
        "tool_count": TOOL_COUNT,
        "manifest": PLATFORM_CAPABILITIES,
        "features": FEATURE_FLAGS,
    }


@api_router.post("/channels/{channel_id}/collaborate")
async def trigger_collaboration(channel_id: str, request: Request):
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)

    # Super admin gets unlimited access
    from routes.routes_admin import is_super_admin as check_super_admin
    is_admin = await check_super_admin(db, user["user_id"])

    # Billing enforcement via keystone
    if not is_admin:
        from keystone import check_usage, increment_usage
        if not await check_usage(db, user["user_id"], "ai_collaboration"):
            raise HTTPException(402, "Daily AI collaboration limit reached. Upgrade your plan for more.")
        await increment_usage(db, user["user_id"], "ai_collaboration")

    # Billing handled by keystone check_usage above — old free-tier check removed

    if await state_get("collab:active", f"{channel_id}_running"):
        # Human Priority: set pause flag, then start a fresh priority round
        await state_set("collab:priority", channel_id, {
            "pause_requested": True,
            "processed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Brief wait for running agents to yield
        await asyncio.sleep(0.5)
        
        # Mark as processed and run a fresh round with the human's message
        hp = await state_get("collab:priority", channel_id) or {}
        hp["processed"] = True
        await state_set("collab:priority", channel_id, hp)
        asyncio.create_task(run_ai_collaboration(channel_id, user["user_id"],
            called_from_persist=bool((await state_get("collab:persist", channel_id) or {}).get("enabled"))))
        return {"status": "started", "note": "human_priority"}

    # Increment usage
    # Usage increment handled by keystone increment_usage above

    await state_set("collab:active", f"{channel_id}_running", True)
    asyncio.create_task(run_ai_collaboration(channel_id, user["user_id"]))
    return {"status": "started"}

# --- Human Priority Queue ---

@api_router.get("/channels/{channel_id}/human-priority")
async def get_human_priority(channel_id: str, request: Request):
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    hp = await state_get("collab:priority", channel_id) or {}
    return {"active": bool(hp.get("pause_requested") and not hp.get("processed")), "processed": hp.get("processed", False)}

@api_router.post("/channels/{channel_id}/resume-agents")
async def resume_agents(channel_id: str, request: Request):
    """Clear human priority and let agents resume"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    human_priority.pop(channel_id, None)
    return {"resumed": True}

# --- Auto-Collaboration Toggle ---

@api_router.put("/channels/{channel_id}/auto-collab")
async def toggle_auto_collab(channel_id: str, request: Request):
    """Toggle auto-collaboration mode for a channel"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    body = await request.json()
    enabled = body.get("enabled", False)
    
    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {"auto_collab": enabled, "auto_collab_updated_by": user["user_id"]}}
    )
    
    if enabled:
        # Get workspace-level tenant config first, then channel override
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "auto_collab_config": 1, "workspace_id": 1})
        workspace_id = channel.get("workspace_id", "") if channel else ""
        
        # Tenant-level default (set by workspace admin)
        ws_settings = await db.workspace_settings.find_one({"workspace_id": workspace_id}, {"_id": 0})
        tenant_max = ws_settings.get("auto_collab_max_rounds", 10) if ws_settings else 10
        
        # Channel-level override (only if explicitly set, not just defaulting)
        ch_config = channel.get("auto_collab_config") or {} if channel else {}
        if "max_rounds" in ch_config:
            max_rounds = ch_config["max_rounds"]
        else:
            max_rounds = tenant_max
        
        # Clamp to tenant range (5-50)
        max_rounds = min(max(max_rounds, 5), 50)
        
        # Initialize auto-collab session tracking
        auto_collab_sessions[channel_id] = {
            "enabled": True,
            "round": 0,
            "max_rounds": max_rounds,
            "agent_rounds": {},
            "user_id": user["user_id"],
        }
        # Start auto-collaboration loop
        if not await state_get("collab:active", f"{channel_id}_running"):
            # Usage increment handled by keystone increment_usage
            await state_set("collab:active", f"{channel_id}_running", True)
            asyncio.create_task(run_auto_collaboration_loop(channel_id, user["user_id"]))
    else:
        await state_delete("collab:auto", channel_id)
    
    return {"auto_collab": enabled, "channel_id": channel_id}

@api_router.get("/channels/{channel_id}/auto-collab")
async def get_auto_collab_status(channel_id: str, request: Request):
    """Get auto-collaboration status for a channel"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "auto_collab": 1, "auto_collab_config": 1, "workspace_id": 1})
    enabled = channel.get("auto_collab", False) if channel else False
    config = channel.get("auto_collab_config") or {} if channel else {}
    workspace_id = channel.get("workspace_id", "") if channel else ""
    ws_settings = await db.workspace_settings.find_one({"workspace_id": workspace_id}, {"_id": 0})
    tenant_max = ws_settings.get("auto_collab_max_rounds", 10) if ws_settings else 10
    session = auto_collab_sessions.get(channel_id, {})
    return {
        "enabled": enabled,
        "round": session.get("round", 0),
        "max_rounds": config.get("max_rounds", tenant_max),
        "tenant_max_rounds": tenant_max,
        "agent_rounds": session.get("agent_rounds") or {},
        "config": config,
    }

@api_router.put("/channels/{channel_id}/auto-collab-config")
async def update_auto_collab_config(channel_id: str, request: Request):
    """Configure auto-collaboration limits per channel"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    body = await request.json()
    config = {}
    if "max_rounds" in body:
        config["max_rounds"] = min(max(int(body["max_rounds"]), 1), 50)
    if "agent_limits" in body:
        config["agent_limits"] = body["agent_limits"]  # {agent_key: max_rounds}
    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {"auto_collab_config": config}}
    )
    return {"channel_id": channel_id, "config": config}

# --- Auto Collaborate Persist (runs indefinitely with throttling) ---


@api_router.put("/channels/{channel_id}/auto-collab-persist")
async def toggle_persist(channel_id: str, request: Request):
    """Toggle persistent auto-collaboration — runs until turned off"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    body = await request.json()
    enabled = body.get("enabled", False)

    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {"auto_collab_persist": enabled}}
    )

    if enabled:
        # Force-clear any stale collaboration flags to avoid persist never starting
        await state_delete("collab:active", f"{channel_id}_running")
        await state_delete("collab:stop", channel_id)
        
        # Flush pending batch from previous session
        pending = (await state_get("collab:batch", channel_id) or [])
        if not pending:
            # Check DB for persisted batch
            db_batch = await db.pending_collab_batch.find_one({"channel_id": channel_id}, {"_id": 0})
            if db_batch:
                pending = db_batch.get("messages") or []
                await db.pending_collab_batch.delete_many({"channel_id": channel_id})
        
        # Post batched messages from the previous session
        if pending:
            for msg in pending:
                msg["batched"] = True
                msg["content"] = f"_[Resumed from batch]_ {msg.get('content', '')}"
                await db.messages.insert_one(msg)
            logger.info(f"Flushed {len(pending)} batched messages for {channel_id}")
        
        await state_set("collab:persist", channel_id, {
            "enabled": True,
            "round": 0,
            "delay": 3,
            "min_delay": 3,
            "max_delay": 120,
            "consecutive_errors": 0,
            "status": "starting",
            "user_id": user["user_id"],
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        await state_set("collab:active", f"{channel_id}_running", True)
        asyncio.create_task(run_persist_collaboration(channel_id, user["user_id"]))
        
        # Post a visible start message so user sees feedback
        await db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "system",
            "sender_id": "system",
            "sender_name": "System",
            "content": f"_Persistent collaboration enabled by {user.get('name', 'a user')}. Agents will continuously collaborate until stopped._",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return {"persist": True, "status": "started"}
    else:
        # HARD STOP: Signal all in-flight agents to batch their responses
        await state_set("collab:stop", channel_id, True)
        await state_delete("collab:persist", channel_id)
        await state_delete("collab:auto", channel_id)
        await state_delete("collab:active", f"{channel_id}_running")
        
        # Also clear any per-agent thinking flags to prevent stragglers
        keys_to_clear = [k for k in active_collaborations if k.startswith(f"{channel_id}_")]
        for k in keys_to_clear:
            await state_delete("collab:active", k)
        
        # Count batched items
        batched_count = len(await state_get("collab:batch", channel_id) or [])
        
        await db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "system",
            "sender_id": "system",
            "sender_name": "System",
            "content": f"_Persistent collaboration **hard stopped** by {user.get('name', 'a user')}. All agents halted.{f' {batched_count} pending responses batched for resume.' if batched_count else ''}_",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Save pending batch to DB for persistence across restarts
        pending_batch_data = await state_get("collab:batch", channel_id) or []
        if pending_batch_data:
            await db.pending_collab_batch.delete_many({"channel_id": channel_id})
            ch_data = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
            await db.pending_collab_batch.insert_one({
                "channel_id": channel_id,
                "workspace_id": ch_data.get("workspace_id", "") if ch_data else "",
                "messages": await state_get("collab:batch", channel_id) or [],
                "batched_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user["user_id"],
            })
        
        # Clear hard stop after a brief delay (let in-flight requests see it)
        async def _clear_hard_stop():
            await asyncio.sleep(5)
            await state_delete("collab:stop", channel_id)
        asyncio.create_task(_clear_hard_stop())
        
        return {"persist": False, "status": "hard_stopped", "batched": batched_count}

@api_router.get("/channels/{channel_id}/auto-collab-persist")
async def get_persist_status(channel_id: str, request: Request):
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "auto_collab_persist": 1})
    enabled = channel.get("auto_collab_persist", False) if channel else False
    session = await state_get("collab:persist", channel_id) or {}
    return {
        "enabled": enabled,
        "round": session.get("round", 0),
        "delay": session.get("delay", 0),
        "status": session.get("status", "idle"),
        "consecutive_errors": session.get("consecutive_errors", 0),
        "started_at": session.get("started_at"),
        "pending_batch": len(await state_get("collab:batch", channel_id) or []),
        "hard_stopped": await state_get("collab:stop", channel_id),
    }

@api_router.put("/channels/{channel_id}/agent-toggle")
async def toggle_channel_agent(channel_id: str, request: Request):
    """Enable or disable a specific AI agent in a channel"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    body = await request.json()
    agent_key = body.get("agent_key", "")
    enabled = body.get("enabled", True)
    
    if not agent_key:
        raise HTTPException(400, "agent_key required")
    
    if enabled:
        # Remove from disabled list
        await db.channels.update_one(
            {"channel_id": channel_id},
            {"$pull": {"disabled_agents": agent_key}}
        )
    else:
        # Add to disabled list
        await db.channels.update_one(
            {"channel_id": channel_id},
            {"$addToSet": {"disabled_agents": agent_key}}
        )
    
    return {"agent_key": agent_key, "enabled": enabled, "channel_id": channel_id}

@api_router.get("/channels/{channel_id}/disabled-agents")
async def get_disabled_agents(channel_id: str, request: Request):
    """Get list of disabled agents for a channel"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "disabled_agents": 1})
    return {"disabled_agents": channel.get("disabled_agents") or [] if channel else []}

# --- Channel Roles (TPM / Architect) ---

@api_router.get("/channels/{channel_id}/roles")
async def get_channel_roles(channel_id: str, request: Request):
    """Get TPM and Architect role assignments for a channel"""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "channel_roles": 1})
    roles = channel.get("channel_roles") or {} if channel else {}
    return {
        "tpm": roles.get("tpm"),
        "architect": roles.get("architect"),
        "browser_operator": roles.get("browser_operator"),
        "qa": roles.get("qa") or [],
        "security": roles.get("security"),
    }

@api_router.put("/channels/{channel_id}/roles")
async def set_channel_roles(channel_id: str, request: Request):
    """Set channel roles. TPM/Architect/Browser/Security = single agent. QA = list of agents."""
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    body = await request.json()
    updates = {}
    if "tpm" in body:
        updates["channel_roles.tpm"] = body["tpm"]
    if "architect" in body:
        updates["channel_roles.architect"] = body["architect"]
    if "browser_operator" in body:
        updates["channel_roles.browser_operator"] = body["browser_operator"]
    if "qa" in body:
        updates["channel_roles.qa"] = body["qa"] if isinstance(body["qa"], list) else [body["qa"]] if body["qa"] else []
    if "security" in body:
        updates["channel_roles.security"] = body["security"]
    if not updates:
        raise HTTPException(400, "Provide 'tpm' and/or 'architect' agent key")
    await db.channels.update_one({"channel_id": channel_id}, {"$set": updates})
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "channel_roles": 1})
    roles = channel.get("channel_roles") or {} if channel else {}
    return {"tpm": roles.get("tpm"), "architect": roles.get("architect"), "browser_operator": roles.get("browser_operator"), "qa": roles.get("qa") or [], "security": roles.get("security")}

async def run_auto_collaboration_loop(channel_id: str, user_id: str):
    """Run auto-collaboration loop — agents keep collaborating until toggled off or limits hit"""
    try:
        session = auto_collab_sessions.get(channel_id)
        if not session:
            return
        
        max_overall_rounds = session.get("max_rounds", 10)
        
        for round_num in range(1, max_overall_rounds + 1):
            # Check if still enabled
            session = auto_collab_sessions.get(channel_id)
            if not session or not session.get("enabled"):
                logger.info(f"Auto-collab disabled for {channel_id}, stopping at round {round_num}")
                break
            
            session["round"] = round_num
            logger.info(f"Auto-collab round {round_num} for {channel_id}")
            
            # Human Priority Check — pause if human sent a message
            hp = await state_get("collab:priority", channel_id)
            if hp and hp.get("pause_requested") and not hp.get("processed"):
                logger.info(f"Auto-collab pausing for human priority in {channel_id}")
                for _ in range(30):
                    hp = await state_get("collab:priority", channel_id)
                    if not hp or hp.get("processed"):
                        break
                    await asyncio.sleep(1)
                human_priority.pop(channel_id, None)
                continue
            
            # Run one round of collaboration
            await run_ai_collaboration(channel_id, user_id, auto_collab_session=session, called_from_persist=True)
            
            # Check again after round completes
            session = auto_collab_sessions.get(channel_id)
            if not session or not session.get("enabled"):
                break
            
            # Check if all agents have hit their limits
            channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "ai_agents": 1})
            if channel:
                all_maxed = True
                for agent_key in channel.get("ai_agents") or []:
                    agent_rounds = (session.get("agent_rounds") or {}).get(agent_key, 0)
                    max_for_agent = AI_MODELS.get(agent_key, {}).get("auto_collab_max_rounds", 5)
                    if agent_rounds < max_for_agent:
                        all_maxed = False
                        break
                if all_maxed:
                    logger.info(f"All agents maxed out for {channel_id}")
                    break
            
            # Brief pause between rounds
            await asyncio.sleep(3)
        
        # Post completion message
        final_round = auto_collab_sessions.get(channel_id, {}).get("round", 0)
        await db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "system",
            "sender_id": "system",
            "sender_name": "System",
            "content": f"_Auto-collaboration completed after {final_round} rounds._",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Disable auto-collab
        await state_delete("collab:auto", channel_id)
        await db.channels.update_one(
            {"channel_id": channel_id},
            {"$set": {"auto_collab": False}}
        )
        
    except Exception as e:
        logger.error(f"Auto-collab loop error: {e}")
        await state_delete("collab:auto", channel_id)
    finally:
        await state_delete("collab:active", f"{channel_id}_running")

@api_router.get("/channels/{channel_id}/status")
async def get_collaboration_status(channel_id: str, request: Request):
    user = await get_current_user(request)
    from nexus_utils import require_channel_access
    await require_channel_access(db, user, channel_id)
    
    # Get channel to know which agents are active
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
    
    status = {}
    if channel:
        for agent_key in channel.get("ai_agents") or []:
            collab_key = f"{channel_id}_{agent_key}"
            status[agent_key] = await state_get("collab:active", collab_key) or "idle"
    
    is_running = await state_get("collab:active", f"{channel_id}_running")
    return {"agents": status, "is_running": is_running}

# ============ Health ============

async def health():
    return {"status": "ok"}

# ============ Route Registry ============
# All route modules registered via centralized registry
from route_registry import register_all_routes
register_all_routes(app, api_router, db, get_current_user, ws_manager, AI_MODELS)


app.include_router(api_router)

# API v1 alias — redirect /api/v1/* to /api/* for versioned clients

@app.middleware("http")
async def api_version_alias(request: Request, call_next):
    if request.url.path.startswith("/api/v1/"):
        new_path = request.url.path.replace("/api/v1/", "/api/", 1)
        request.scope["path"] = new_path
        request.scope["raw_path"] = new_path.encode("utf-8")
    return await call_next(request)

async def _graceful_shutdown():
    """Single unified shutdown handler."""
    logger.info("Graceful shutdown initiated...")
    # 1. Close all browser sessions
    try:
        from routes.routes_nexus_browser import close_all_sessions
        await close_all_sessions()
    except Exception as e:
        logger.warning(f"Browser cleanup: {e}")
    # 2. Close WebSocket connections
    for ch_id, conns in ws_manager.connections.items():
        for ws in conns:
            try:
                await ws.close(code=1001)
            except Exception as _e:
                import logging; logging.getLogger("server").warning(f"Suppressed: {_e}")
    # 3. Close MongoDB connection pool
    client.close()
    # 4. Close shared HTTP client pool
    try:
        from http_pool import close_http_client
        await close_http_client()
    except Exception as _e:
        import logging; logging.getLogger("server").warning(f"Suppressed: {_e}")
    logger.info("Shutdown complete")

async def _create_indexes():
    """Create MongoDB indexes for production performance"""
    from instance_registry import init_instance_id
    await init_instance_id(_raw_db)

    from db_indexes import create_all_indexes
    await create_all_indexes(db)

    # Run database migrations
    from db_migrations import run_migrations
    await run_migrations(db)

    # Load platform profile
    from platform_profile import load_profile_from_db
    await load_profile_from_db(db)

    # Wire event bus audit consumer — logs all events to audit_log
    from keystone import event_bus
    async def _audit_all_events(payload):
        try:
            safe = {k: v for k, v in payload.items() if not str(k).startswith("$")}
            safe.pop("_id", None)
            await db.audit_log.insert_one(safe)
        except Exception as _e:
            import logging; logging.getLogger("server").warning(f"Suppressed: {_e}")
    event_bus.on("*", _audit_all_events)

    # Ensure super admin has password login (runs every startup, idempotent)
    # Password MUST come from environment variable - never hardcode credentials
    try:
        import bcrypt as _bcrypt
        _sa_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
        _sa_init_pw = os.environ.get("SUPER_ADMIN_INIT_PASSWORD", "")
        if _sa_email and _sa_init_pw:
            _sa_user = await db.users.find_one(
                {"$or": [{"email": _sa_email}, {"email": _sa_email.lower()}]},
                {"_id": 0, "password_hash": 1, "email": 1}
            )
            if _sa_user and not _sa_user.get("password_hash"):
                if len(_sa_init_pw) < 12:
                    logger.error("SUPER_ADMIN_INIT_PASSWORD must be >= 12 chars. Skipping.")
                else:
                    _pw_hash = _bcrypt.hashpw(_sa_init_pw.encode(), _bcrypt.gensalt()).decode()
                    await db.users.update_one(
                        {"email": _sa_user["email"]},
                        {"$set": {"password_hash": _pw_hash, "auth_type": "both", "platform_role": "super_admin"}}
                    )
                    logger.info(f"Startup: Set initial password for super admin"
                                f" {_sa_user['email']} - change immediately")
        elif _sa_email and not _sa_init_pw:
            logger.info("SUPER_ADMIN_INIT_PASSWORD not set - admin must use OAuth"
                        " or forgot-password flow")
    except Exception as _e:
        logger.warning(f"Super admin password check: {_e}")

    # Background task wrapper with resilience + distributed locking
    async def _resilient_task(name, coro_fn, interval):
        """Run a background task with auto-restart on crash + distributed lock."""
        while True:
            try:
                from redis_client import acquire_lock, release_lock
                if not await acquire_lock(f"task_{name}", ttl=interval + 60):
                    await asyncio.sleep(interval)
                    continue
                try:
                    await coro_fn()
                finally:
                    await release_lock(f"task_{name}")
            except Exception as e:
                logger.error(f"Background task '{name}' crashed: {e}. Restarting in 60s.")
                await asyncio.sleep(60)
                continue
            await asyncio.sleep(interval)

    # Start background schedule checker
    from routes.routes_agent_schedules import run_schedule_checker
    async def _run_schedule_checker():
        await run_schedule_checker(db, AI_MODELS)
    asyncio.create_task(_resilient_task("schedule_checker", _run_schedule_checker, 60))

    async def _session_cleanup():
        result = await db.user_sessions.delete_many(
            {"expires_at": {"$lt": datetime.now(timezone.utc).isoformat()}}
        )
        if result.deleted_count > 0:
            logger.info(f"Cleaned up {result.deleted_count} expired sessions")

    async def _reporting_work():
        from routes.routes_reporting import compute_rollups, run_alerting_check, run_scheduled_reports
        await compute_rollups(db)
        await run_alerting_check(db)
        await run_scheduled_reports(db)

    asyncio.create_task(_resilient_task("session_cleanup", _session_cleanup, 3600))
    asyncio.create_task(_resilient_task("reporting_rollup", _reporting_work, 3600))

    # Orchestration schedule checker — runs every 60 seconds
    async def _orch_schedule_check():
        from routes.routes_orch_schedules import run_orchestration_schedules
        await run_orchestration_schedules(db)
    asyncio.create_task(_resilient_task("orch_schedule_checker", _orch_schedule_check, 60))

    # Cost snapshot batch job — runs every hour
    async def _cost_snapshot_work():
        from cost_batch_job import run_cost_snapshot
        from routes.routes_cost_alerts import check_cost_alerts
        await run_cost_snapshot(db)
        await check_cost_alerts(db)
    asyncio.create_task(_resilient_task("cost_snapshot", _cost_snapshot_work, 3600))

    # Training auto-refresh — re-crawl stale sources daily
    async def _training_auto_refresh():
        from datetime import timedelta as _td
        agents = await db.nexus_agents.find(
            {"training.auto_refresh": True, "training.enabled": True},
            {"_id": 0, "agent_id": 1, "workspace_id": 1, "skills": 1, "training": 1}
        ).to_list(50)
        for agent in agents:
            interval = (agent.get("training") or {}).get("refresh_interval_days", 30)
            last = (agent.get("training") or {}).get("last_trained")
            if last:
                from datetime import datetime as _dt
                try:
                    last_dt = _dt.fromisoformat(last.replace("Z", "+00:00"))
                    if _dt.now(timezone.utc) - last_dt < _td(days=interval):
                        continue
                except Exception as _e:
                    import logging; logging.getLogger("server").warning(f"Suppressed: {_e}")
            # Find URLs from previous sessions to re-crawl
            sessions = await db.agent_training_sessions.find(
                {"agent_id": agent["agent_id"], "source_type": {"$in": ["url", "topics"]}},
                {"_id": 0, "urls": 1, "manual_urls": 1}
            ).sort("created_at", -1).limit(3).to_list(3)
            urls = []
            for s in sessions:
                urls.extend(s.get("urls") or [])
                urls.extend(s.get("manual_urls") or [])
            if urls:
                from agent_training_crawler import fetch_page_content, chunk_content, tokenize_for_retrieval, classify_category, extract_tags, classify_source_authority, score_chunk_quality, _extract_domain
                session_id = f"refresh_{uuid.uuid4().hex[:12]}"
                total = 0
                for url in list(set(urls))[:5]:
                    page = await fetch_page_content(url)
                    if page.get("error"):
                        continue
                    chunks = chunk_content(page.get("text", ""), page.get("title", ""))
                    domain = _extract_domain(url)
                    auth = classify_source_authority(domain)
                    for cd in chunks:
                        quality = await score_chunk_quality(cd["content"], "refresh")
                        if quality < 0.3:
                            continue
                        tokens = tokenize_for_retrieval(cd["content"])
                        await db.agent_knowledge.insert_one({
                            "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                            "agent_id": agent["agent_id"], "workspace_id": agent["workspace_id"],
                            "session_id": session_id,
                            "content": cd["content"], "summary": cd["content"][:200],
                            "category": classify_category(cd["content"]),
                            "topic": "auto-refresh", "tags": ["auto-refresh"],
                            "source": {"type": "web", "url": url, "title": page.get("title", ""), "domain": domain},
                            "tokens": tokens, "token_count": cd.get("token_count", len(tokens)),
                            "quality_score": quality, "source_authority": auth,
                            "flagged": False, "times_retrieved": 0,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                        total += 1
                if total > 0:
                    await db.nexus_agents.update_one(
                        {"agent_id": agent["agent_id"]},
                        {"$set": {"training.last_trained": datetime.now(timezone.utc).isoformat()},
                         "$inc": {"training.total_chunks": total}}
                    )
                    # Post-refresh enrichment (AI summary + BM25 embeddings)
                    try:
                        from routes.routes_agent_training import _post_training_enrich
                        await _post_training_enrich(db, agent["agent_id"], agent["workspace_id"], session_id)
                    except Exception as enrich_err:
                        logger.debug(f"Post-refresh enrichment skipped: {enrich_err}")
                    logger.info(f"Auto-refresh: {total} chunks for agent {agent['agent_id']}")
    asyncio.create_task(_resilient_task("training_auto_refresh", _training_auto_refresh, 86400))

    # Leaderboard snapshot — daily
    async def _leaderboard_snapshot():
        agents = await db.nexus_agents.find(
            {}, {"_id": 0, "agent_id": 1, "name": 1, "evaluation.overall_score": 1, "stats.total_messages": 1, "base_model": 1, "workspace_id": 1}
        ).limit(100).to_list(100)
        ranked = sorted(agents, key=lambda a: (a.get("evaluation") or {}).get("overall_score", 0), reverse=True)
        data = [{"rank": i+1, "agent_id": a.get("agent_id"), "name": a.get("name"), "score": (a.get("evaluation") or {}).get("overall_score", 0)} for i, a in enumerate(ranked[:25])]
        await db.leaderboard_snapshots.insert_one({
            "snapshot_id": f"lbs_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data, "total_agents": len(agents),
        })
    asyncio.create_task(_resilient_task("leaderboard_snapshot", _leaderboard_snapshot, 86400))

    # Auto-resume persistent collaboration sessions from DB
    try:
        persist_channels = await db.channels.find(
            {"auto_collab_persist": True},
            {"_id": 0, "channel_id": 1, "workspace_id": 1}
        ).to_list(50)
        for ch in persist_channels:
            channel_id = ch["channel_id"]
            # Find the workspace owner to use as the user_id
            ws = await db.workspaces.find_one({"workspace_id": ch.get("workspace_id", "")}, {"_id": 0, "owner_id": 1})
            user_id = ws.get("owner_id", "") if ws else ""
            if user_id and channel_id not in persist_sessions:
                await state_set("collab:persist", channel_id, {
                    "enabled": True, "round": 0, "delay": 5,
                    "min_delay": 3, "max_delay": 120,
                    "consecutive_errors": 0, "status": "resuming",
                    "user_id": user_id,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                })
                await state_set("collab:active", f"{channel_id}_running", True)
                asyncio.create_task(run_persist_collaboration(channel_id, user_id))
                logger.info(f"Resumed persist collaboration for {channel_id}")
        if persist_channels:
            logger.info(f"Resumed {len(persist_channels)} persistent collaboration sessions")
    except Exception as e:
        logger.warning(f"Persist resume failed: {e}")
