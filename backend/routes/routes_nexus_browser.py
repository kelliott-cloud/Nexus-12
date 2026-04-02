"""Nexus Browser — Server-side Firefox browser control via Playwright.

Agents can navigate, click, type, and take screenshots of web pages.
Browser sessions are per-channel with a designated "Browser Operator" agent.
When agents need human help, they post a help request in the channel.
"""
import os
import uuid
import base64
import asyncio
import logging
from datetime import datetime, timezone, timedelta
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

logger = logging.getLogger(__name__)
if not PLAYWRIGHT_AVAILABLE:
    logger.warning("Playwright not installed — Nexus Browser will be disabled.")

# Active browser sessions: channel_id -> session dict
_browser_sessions = {}
_playwright_instance = None
_browser_instance = None


async def _get_browser():
    """Get or create the shared Firefox browser instance."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Nexus Browser requires Playwright. Install: pip install playwright && playwright install firefox")
    global _playwright_instance, _browser_instance
    if _browser_instance and _browser_instance.is_connected():
        return _browser_instance
    _playwright_instance = await async_playwright().start()
    _browser_instance = await _playwright_instance.firefox.launch(headless=True)
    logger.info("Nexus Browser (Firefox) launched")
    return _browser_instance


async def create_session(channel_id: str, url: str = "about:blank"):
    """Create a new browser session for a channel."""
    if channel_id in _browser_sessions:
        await close_session(channel_id)

    browser = await _get_browser()
    context = await browser.new_context(viewport={"width": 1280, "height": 800})
    page = await context.new_page()

    if url and url != "about:blank":
        try:
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning(f"Navigation to {url} failed: {e}")

    _browser_sessions[channel_id] = {
        "session_id": f"bsess_{uuid.uuid4().hex[:12]}",
        "channel_id": channel_id,
        "context": context,
        "page": page,
        "current_url": page.url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "help_requested": False,
        "help_message": "",
    }
    return _browser_sessions[channel_id]["session_id"]


async def close_session(channel_id: str):
    """Close a browser session."""
    session = _browser_sessions.pop(channel_id, None)
    if session:
        try:
            await session["context"].close()
        except Exception as _e:
            logger.debug(f"Non-critical: {_e}")


async def shutdown_browser():
    """Shutdown all browser sessions and the browser instance."""
    global _browser_instance, _playwright_instance
    for ch_id in list(_browser_sessions.keys()):
        await close_session(ch_id)


async def close_all_sessions():
    """Alias for shutdown_browser — called during app shutdown."""
    await shutdown_browser()
    if _browser_instance:
        try:
            await _browser_instance.close()
        except Exception as _e:
            logger.debug(f"Non-critical: {_e}")
        _browser_instance = None
    if _playwright_instance:
        try:
            await _playwright_instance.stop()
        except Exception as _e:
            logger.debug(f"Non-critical: {_e}")
        _playwright_instance = None
    logger.info("Nexus Browser shutdown complete")


async def cleanup_stale_sessions():
    """Remove browser sessions idle for more than 30 minutes."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    stale = [ch_id for ch_id, s in _browser_sessions.items() if s.get("last_activity", s.get("created_at", "")) < cutoff]
    for ch_id in stale:
        logger.info(f"Cleaning up stale browser session: {ch_id}")
        await close_session(ch_id)
    return len(stale)


async def navigate(channel_id: str, url: str):
    """Navigate the browser to a URL."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session. Open the Nexus Browser first."}
    try:
        await session["page"].goto(url, timeout=15000, wait_until="domcontentloaded")
        session["current_url"] = session["page"].url
        session["last_activity"] = datetime.now(timezone.utc).isoformat()
        return {"url": session["page"].url, "title": await session["page"].title()}
    except Exception as e:
        return {"error": f"Navigation failed: {str(e)[:200]}"}


async def click_element(channel_id: str, selector: str):
    """Click an element on the page."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session."}
    try:
        await session["page"].click(selector, timeout=5000)
        await session["page"].wait_for_timeout(500)
        session["current_url"] = session["page"].url
        return {"clicked": selector, "url": session["page"].url}
    except Exception as e:
        return {"error": f"Click failed on '{selector}': {str(e)[:200]}"}


async def type_text(channel_id: str, selector: str, text: str):
    """Type text into an input field."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session."}
    try:
        await session["page"].fill(selector, text, timeout=5000)
        return {"typed": text[:50], "selector": selector}
    except Exception as e:
        return {"error": f"Type failed on '{selector}': {str(e)[:200]}"}


async def take_screenshot(channel_id: str):
    """Take a screenshot and return as base64."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session."}
    try:
        screenshot = await session["page"].screenshot(type="jpeg", quality=60)
        b64 = base64.b64encode(screenshot).decode("utf-8")
        return {
            "screenshot": b64,
            "url": session["page"].url,
            "title": await session["page"].title(),
        }
    except Exception as e:
        return {"error": f"Screenshot failed: {str(e)[:200]}"}


async def get_page_text(channel_id: str, max_chars: int = 3000):
    """Extract visible text from the current page."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session."}
    try:
        text = await session["page"].inner_text("body", timeout=5000)
        return {
            "text": text[:max_chars],
            "url": session["page"].url,
            "title": await session["page"].title(),
            "truncated": len(text) > max_chars,
        }
    except Exception as e:
        return {"error": f"Text extraction failed: {str(e)[:200]}"}


async def request_human_help(channel_id: str, help_message: str):
    """Agent requests human assistance with the browser."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session."}
    session["help_requested"] = True
    session["help_message"] = help_message
    return {"help_requested": True, "message": help_message}


async def get_page_elements(channel_id: str):
    """Get interactive elements on the page (links, buttons, inputs) for agent use."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return {"error": "No browser session."}
    try:
        elements = await session["page"].evaluate("""() => {
            const results = [];
            // Links
            document.querySelectorAll('a[href]').forEach((el, i) => {
                if (i < 20 && el.textContent.trim()) {
                    results.push({type: 'link', text: el.textContent.trim().substring(0, 60), selector: `a:has-text("${el.textContent.trim().substring(0, 30)}")`, href: el.href});
                }
            });
            // Buttons
            document.querySelectorAll('button, [role="button"], input[type="submit"]').forEach((el, i) => {
                if (i < 15) {
                    const text = el.textContent?.trim() || el.value || el.ariaLabel || '';
                    if (text) results.push({type: 'button', text: text.substring(0, 60), selector: el.id ? `#${el.id}` : `button:has-text("${text.substring(0, 30)}")`});
                }
            });
            // Inputs
            document.querySelectorAll('input:not([type="hidden"]), textarea, select').forEach((el, i) => {
                if (i < 15) {
                    const label = el.ariaLabel || el.placeholder || el.name || el.id || '';
                    results.push({type: 'input', label: label.substring(0, 60), selector: el.id ? `#${el.id}` : el.name ? `[name="${el.name}"]` : `input:nth-of-type(${i+1})`, inputType: el.type || 'text'});
                }
            });
            return results;
        }""")
        return {
            "elements": elements,
            "url": session["page"].url,
            "title": await session["page"].title(),
            "count": len(elements),
        }
    except Exception as e:
        return {"error": f"Element extraction failed: {str(e)[:200]}"}


def get_session_info(channel_id: str):
    """Get current session status."""
    session = _browser_sessions.get(channel_id)
    if not session:
        return None
    return {
        "session_id": session["session_id"],
        "current_url": session.get("current_url", "about:blank"),
        "help_requested": session.get("help_requested", False),
        "help_message": session.get("help_message", ""),
        "created_at": session["created_at"],
    }


def register_browser_routes(api_router, db, get_current_user):
    """Register HTTP endpoints for the Nexus Browser."""
    from fastapi import Request, HTTPException

    def _check_available():
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Nexus Browser is not available. Playwright is not installed on this server.", "available": False}
        return None

    async def _verify_channel_access(user, channel_id):
        """Verify user has access to the channel's workspace."""
        from data_guard import TenantIsolation
        has_access = await TenantIsolation.verify_channel_access(db, user["user_id"], channel_id)
        if not has_access:
            raise HTTPException(403, "Access denied")

    @api_router.post("/channels/{channel_id}/browser/open")
    async def open_browser(channel_id: str, request: Request):
        """Open a Nexus Browser session for a channel."""
        err = _check_available()
        if err:
            return err
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        body = await request.json()
        url = body.get("url", "https://www.google.com")
        session_id = await create_session(channel_id, url)
        screenshot = await take_screenshot(channel_id)
        return {
            "session_id": session_id,
            "url": url,
            "screenshot": screenshot.get("screenshot"),
            "title": screenshot.get("title", ""),
        }

    @api_router.post("/channels/{channel_id}/browser/navigate")
    async def browser_navigate(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        body = await request.json()
        url = body.get("url", "")
        if not url:
            raise HTTPException(400, "URL required")
        result = await navigate(channel_id, url)
        if "error" in result:
            return result
        screenshot = await take_screenshot(channel_id)
        result["screenshot"] = screenshot.get("screenshot")
        return result

    @api_router.post("/channels/{channel_id}/browser/click")
    async def browser_click(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        body = await request.json()
        selector = body.get("selector", "")
        result = await click_element(channel_id, selector)
        screenshot = await take_screenshot(channel_id)
        result["screenshot"] = screenshot.get("screenshot")
        return result

    @api_router.post("/channels/{channel_id}/browser/type")
    async def browser_type(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        body = await request.json()
        selector = body.get("selector", "")
        text = body.get("text", "")
        result = await type_text(channel_id, selector, text)
        screenshot = await take_screenshot(channel_id)
        result["screenshot"] = screenshot.get("screenshot")
        return result

    @api_router.get("/channels/{channel_id}/browser/screenshot")
    async def browser_screenshot(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        return await take_screenshot(channel_id)

    @api_router.get("/channels/{channel_id}/browser/text")
    async def browser_text(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        return await get_page_text(channel_id)

    @api_router.get("/channels/{channel_id}/browser/status")
    async def browser_status(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        info = get_session_info(channel_id)
        return {"active": info is not None, "session": info}

    @api_router.post("/channels/{channel_id}/browser/close")
    async def close_browser(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        await close_session(channel_id)
        return {"closed": True}

    @api_router.post("/channels/{channel_id}/browser/help-resolve")
    async def resolve_help(channel_id: str, request: Request):
        """Human resolves an agent's help request."""
        user = await get_current_user(request)
        await _verify_channel_access(user, channel_id)
        session = _browser_sessions.get(channel_id)
        if session:
            session["help_requested"] = False
            session["help_message"] = ""
        return {"resolved": True}
