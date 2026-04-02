"""User preferences, language, and desktop download routes — extracted from server.py (N7-019)."""
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path


def register_user_prefs_routes(api_router, db, get_current_user):

    @api_router.put("/user/language")
    async def update_language(request: Request):
        """Update user's language preference"""
        user = await get_current_user(request)
        data = await request.json()
        lang = data.get("language", "en")
        from nexus_config import SUPPORTED_LANGUAGES_I18N
        if lang not in SUPPORTED_LANGUAGES_I18N:
            raise HTTPException(400, f"Invalid language. Supported: {', '.join(SUPPORTED_LANGUAGES_I18N)}")
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"language": lang}}
        )
        return {"status": "updated", "language": lang}

    @api_router.put("/user/preferences")
    async def update_user_preferences(request: Request):
        """Update user preferences (theme, pinned panels, etc.)"""
        user = await get_current_user(request)
        data = await request.json()
        updates = {}
        valid_themes = {"dark", "light", "system", "beach", "forest", "desert", "river", "mountain",
                        "sunset", "aurora", "tropical", "arctic", "volcano", "cherry-blossom",
                        "lavender", "midnight", "coral-reef", "savanna", "bamboo", "glacier",
                        "autumn", "nebula", "rainforest",
                        "claude", "chatgpt", "gemini", "perplexity", "deepseek", "mistral",
                        "grok", "copilot", "pi", "notebooklm", "qwen", "llama", "cohere"}
        if "theme" in data and data["theme"] in valid_themes:
            updates["theme"] = data["theme"]
        if "pinned_panels" in data and isinstance(data["pinned_panels"], dict):
            updates["pinned_panels"] = data["pinned_panels"]
        if updates:
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {f"preferences.{k}": v for k, v in updates.items()}}
            )
        return {"status": "updated", **updates}

    @api_router.get("/user/preferences")
    async def get_user_preferences(request: Request):
        """Get user preferences"""
        user = await get_current_user(request)
        prefs = user.get("preferences") or {}
        return {"theme": prefs.get("theme", "dark"), "language": user.get("language", "en"), "pinned_panels": prefs.get("pinned_panels") or {}}

    @api_router.get("/download/desktop/{arch}")
    async def download_desktop(arch: str):
        """Download the Nexus desktop app for Windows"""
        if arch not in ("x64", "ia32"):
            raise HTTPException(400, "Invalid architecture. Use x64 or ia32")
        zip_path = Path(__file__).parent.parent / "static" / f"Nexus-Desktop-Setup-{arch}.zip"
        if not zip_path.exists():
            raise HTTPException(404, "Desktop build not available for this architecture")
        return FileResponse(
            path=str(zip_path),
            filename=f"Nexus-Desktop-Setup-{arch}.zip",
            media_type="application/zip"
        )
