"""Platform Profile — Instance-level configuration schema. Sits ABOVE org/workspace module config:

  Platform Profile -> Org Defaults -> Workspace Modules -> User Plan

Feature states:
  "on"  — Enabled by default. Visible in sidebar. Routes active.
  "opt" — Available but hidden by default. Admin can enable per workspace.
  "off" — Removed from instance. Routes return 404. No UI trace.
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_profile: dict = {}
_loaded = False

FEATURE_ROUTE_MAP = {
    "persistent_collaboration": ["/auto-collab-persist"],
    "channel_roles": ["/channels/{channel_id}/roles"],
    "agent_studio": ["/agent-studio"],
    "agent_training": ["/agent-training", "/agent-knowledge"],
    "agent_evaluation": ["/agents/{agent_id}/evaluate"],
    "agent_versioning": ["/agent-versions"],
    "orchestration": ["/orchestrations", "/orchestration-templates"],
    "a2a_pipelines": ["/a2a"],
    "operator_mode": ["/operator"],
    "agent_arena": ["/arena"],
    "agent_dojo": ["/dojo"],
    "deployments": ["/deployments"],
    "projects": ["/projects", "/project-tasks", "/milestones"],
    "gantt_chart": ["/planner"],
    "ideation": ["/ideation"],
    "code_repository": ["/code", "/repo"],
    "wiki_docs": ["/wiki"],
    "workflow_engine": ["/workflows"],
    "webhooks": ["/webhooks"],
    "code_execution": ["/execute"],
    "github_integration": ["/github"],
    "image_generation": ["/image-gen"],
    "video_generation": ["/video"],
    "tts_audio": ["/tts", "/audio"],
    "content_generation": ["/content-gen"],
    "social_publishing": ["/social"],
    "roi_calculator": ["/roi"],
    "reporting_engine": ["/reports", "/reporting"],
    "sso_saml": ["/sso"],
    "scim_provisioning": ["/scim"],
    "soc2_compliance": ["/soc2"],
    "cloud_storage": ["/cloud-storage", "/drive"],
    "communication_plugins": ["/plugins"],
    "smart_inbox": ["/mail"],
    "desktop_bridge": ["/bridge"],
    "nexus_browser": ["/browser"],
    "navc_turboquant": ["/turboquant"],
    "fine_tuning": ["/finetune"],
    "marketplace": ["/marketplace"],
    "revenue_sharing": ["/revenue-sharing"],
}

DEFAULT_PROFILE = {
    "profile_id": "full_platform",
    "profile_name": "Full Platform (All Features)",
    "profile_version": "1.0",
    "branding": {
        "platform_name": "Nexus Cloud",
        "tagline": "AI Collaboration Platform",
        "logo_url": None,
        "primary_color": "#1F3864",
    },
    "features": {k: "on" for k in FEATURE_ROUTE_MAP},
    "ai_models": {
        "available": ["chatgpt", "claude", "gemini", "deepseek", "grok", "mistral",
                      "cohere", "groq", "perplexity", "mercury", "pi", "manus",
                      "qwen", "kimi", "llama", "glm", "cursor", "notebooklm", "copilot"],
        "hidden": [],
    },
    "integrations": {k: "on" for k in [
        "github", "cloud_storage", "slack", "discord", "social_platforms",
        "email_services", "desktop_bridge", "nexus_browser",
    ]},
    "billing": {
        "product_line": "full",
        "stripe_enabled": True,
        "managed_keys_enabled": True,
    },
    "onboarding": {
        "wizard_enabled": True,
        "default_persona": None,
        "show_persona_selection": True,
    },
}


def load_profile(db=None):
    global _profile, _loaded
    profile_id = os.environ.get("PLATFORM_PROFILE", "")
    if profile_id:
        profile_dir = Path(__file__).parent / "platform_profiles"
        profile_path = profile_dir / f"{profile_id}.json"
        if profile_path.exists():
            with open(profile_path) as f:
                _profile = json.load(f)
                _loaded = True
                logger.info(f"Platform profile loaded from file: {profile_id}")
                return _profile
    _profile = DEFAULT_PROFILE.copy()
    _loaded = True
    logger.info("Platform profile: full_platform (default)")
    return _profile


async def load_profile_from_db(db):
    global _profile, _loaded
    try:
        doc = await db.platform_settings.find_one(
            {"setting_id": "platform_profile"}, {"_id": 0})
        if doc and doc.get("profile"):
            _profile = doc["profile"]
            _loaded = True
            logger.info(f"Platform profile loaded from DB: {_profile.get('profile_id', 'unknown')}")
            return _profile
    except Exception as e:
        logger.warning(f"Failed to load profile from DB: {e}")
    return load_profile()


def get_profile() -> dict:
    if not _loaded:
        load_profile()
    return _profile


def get_feature_state(feature_key: str) -> str:
    profile = get_profile()
    return (profile.get("features") or {}).get(feature_key, "on")


def is_feature_available(feature_key: str) -> bool:
    return get_feature_state(feature_key) != "off"


def is_ai_model_available(model_key: str) -> bool:
    profile = get_profile()
    models = profile.get("ai_models") or {}
    hidden = models.get("hidden") or []
    available = models.get("available") or []
    if model_key in hidden:
        return False
    if available:
        return model_key in available
    return True


def get_route_feature(route_suffix: str) -> Optional[str]:
    for feature_key, prefixes in FEATURE_ROUTE_MAP.items():
        for prefix in prefixes:
            clean_prefix = prefix.split("{")[0]
            if route_suffix.startswith(clean_prefix):
                return feature_key
    return None
