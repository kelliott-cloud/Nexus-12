"""Module Registry — Static configuration defining all Nexus platform modules."""

MODULE_REGISTRY = {
    "core": {
        "module_id": "core", "name": "Core", "description": "AI chat with multiple models, workspace management, file storage, notifications",
        "icon": "message-square", "nav_keys": ["chat", "dashboard", "members", "schedules", "drive"],
        "route_prefixes": ["/channels", "/workspaces", "/messages", "/notifications", "/auth", "/health", "/ai-models", "/user"],
        "min_tier": "free", "monthly_price": 0, "always_on": True, "dependencies": [],
    },
    "plan_track": {
        "module_id": "plan_track", "name": "Plan & Track", "description": "Project management, task boards, timeline views, calendar planning, brainstorming",
        "icon": "kanban", "nav_keys": ["projects", "tasks", "gantt", "planner", "ideation"],
        "route_prefixes": ["/projects", "/project-tasks", "/milestones", "/planner", "/ideation"],
        "min_tier": "starter", "monthly_price": 0, "always_on": False, "dependencies": ["core"],
    },
    "agent_builder": {
        "module_id": "agent_builder", "name": "Agent Builder", "description": "Custom agent creation, skill configuration, training pipelines, evaluation, playground",
        "icon": "bot", "nav_keys": ["agents", "studio", "skill-matrix", "catalog", "training", "skills", "playground", "evaluation"],
        "route_prefixes": ["/nexus-agents", "/agents", "/catalog", "/agent-training", "/agent-skills", "/agent-playground", "/agent-knowledge"],
        "min_tier": "pro", "monthly_price": 15, "always_on": False, "dependencies": ["core"],
    },
    "orchestration": {
        "module_id": "orchestration", "name": "Orchestration", "description": "Multi-agent orchestration, A2A pipelines, operator mode, scheduled runs, benchmarking",
        "icon": "git-branch", "nav_keys": ["orchestration", "a2a-pipelines", "operator", "orch-schedules", "collab-templates", "arena", "benchmarks", "benchmark-compare", "deployments"],
        "route_prefixes": ["/orchestrations", "/a2a", "/operator", "/orchestration-schedules", "/orchestration-templates", "/benchmarks"],
        "min_tier": "pro", "monthly_price": 19, "always_on": False, "dependencies": ["core"],
    },
    "build_code": {
        "module_id": "build_code", "name": "Build & Code", "description": "Code repository, documentation editor, knowledge base, artifacts, webhooks, workflows",
        "icon": "code", "nav_keys": ["code", "docs", "knowledge", "artifacts", "webhooks", "directives", "workflows"],
        "route_prefixes": ["/code", "/wiki", "/knowledge", "/artifacts", "/webhooks", "/directives", "/workflows", "/drive"],
        "min_tier": "starter", "monthly_price": 9, "always_on": False, "dependencies": ["core"],
    },
    "media_studio": {
        "module_id": "media_studio", "name": "Media Studio", "description": "AI image generation, video generation, text-to-speech, centralized media library",
        "icon": "image", "nav_keys": ["images", "video", "audio", "media"],
        "route_prefixes": ["/media", "/image-gen", "/tts", "/video"],
        "min_tier": "pro", "monthly_price": 12, "always_on": False, "dependencies": ["core"],
    },
    "insights": {
        "module_id": "insights", "name": "Insights", "description": "Usage analytics, cost tracking, ROI calculations, performance metrics, quality dashboards",
        "icon": "bar-chart-3", "nav_keys": ["reports", "analytics", "costs", "roi", "revenue", "performance", "leaderboard", "dedup", "training-quality", "repo-analytics", "reviews", "review-analytics", "marketplace-search"],
        "route_prefixes": ["/reports", "/analytics", "/billing/usage", "/roi", "/cost"],
        "min_tier": "starter", "monthly_price": 0, "always_on": False, "dependencies": ["core"],
    },
    "enterprise": {
        "module_id": "enterprise", "name": "Enterprise", "description": "SSO/SAML, security dashboard, marketplace publishing, revenue sharing, org admin, strategic tools",
        "icon": "shield", "nav_keys": ["security", "nx-platform", "strategic"],
        "route_prefixes": ["/admin", "/sso", "/scim", "/revenue-sharing", "/cloudflare", "/openclaw"],
        "min_tier": "team", "monthly_price": 0, "always_on": False, "dependencies": ["core"],
    },
    "model_optimization": {
        "module_id": "model_optimization", "name": "NAVC", "description": "Nexus Adaptive Vector Compression — compression, benchmarking, and deployment for KV-cache and vector-index optimization",
        "icon": "zap", "nav_keys": ["optimization", "compression-profiles", "compression-runs", "compression-compare"],
        "route_prefixes": ["/turboquant"],
        "min_tier": "pro", "monthly_price": 29, "always_on": False, "dependencies": ["core"],
    },
    "smart_inbox": {
        "module_id": "smart_inbox", "name": "Smart Inbox",
        "description": "AI-managed email: connect accounts, triage with agents, delegated actions with governance",
        "icon": "inbox", "nav_keys": ["inbox", "mail-accounts", "mail-rules", "mail-review", "mail-audit"],
        "route_prefixes": ["/mail"],
        "min_tier": "pro", "monthly_price": 19, "always_on": False, "dependencies": ["core"],
    },
    "agent_dojo": {
        "module_id": "agent_dojo", "name": "Agent Dojo",
        "description": "Autonomous agent-to-agent role-playing, mutual training, and synthetic data generation",
        "icon": "dumbbell", "nav_keys": ["dojo", "dojo-scenarios", "dojo-data"],
        "route_prefixes": ["/dojo"],
        "min_tier": "pro", "monthly_price": 29, "always_on": False, "dependencies": ["core"],
    },
    "research_intelligence": {
        "module_id": "research_intelligence", "name": "Research Intelligence",
        "description": "Deep document analysis, citation-linked AI, literature review automation, reference manager connectors",
        "icon": "book-open", "nav_keys": ["research-library", "lit-review", "annotations", "connectors"],
        "route_prefixes": ["/research-lib", "/documents/analyze", "/annotations", "/connectors/zotero", "/connectors/mendeley", "/lit-review"],
        "min_tier": "pro", "monthly_price": 12, "always_on": False, "dependencies": ["core"],
    },
}

PERSONA_BUNDLES = {
    "solo_creator": {"name": "Solo Creator", "description": "For individual creators and freelancers", "modules": ["core", "plan_track"], "bundle_price": 19},
    "developer": {"name": "Developer", "description": "For software developers and engineers", "modules": ["core", "build_code", "plan_track"], "bundle_price": 25},
    "content_team": {"name": "Content Team", "description": "For content and marketing teams", "modules": ["core", "media_studio", "plan_track", "insights"], "bundle_price": 55},
    "ai_power_user": {"name": "AI Power User", "description": "For AI enthusiasts and researchers", "modules": ["core", "agent_builder", "orchestration", "insights"], "bundle_price": 69},
    "engineering_team": {"name": "Engineering Team", "description": "For engineering and product teams", "modules": ["core", "build_code", "plan_track", "agent_builder", "insights"], "bundle_price": 59},
    "everything": {"name": "Everything", "description": "All modules except Enterprise", "modules": ["core", "plan_track", "agent_builder", "orchestration", "build_code", "media_studio", "insights"], "bundle_price": 89},
}

PLAN_TIERS = {"free": 0, "starter": 1, "pro": 2, "team": 3, "enterprise": 4}
PLAN_MODEL_LIMITS = {"free": 3, "starter": 5, "pro": 12, "team": 19, "enterprise": 19}

ALL_AI_MODELS = [
    "claude", "chatgpt", "gemini", "deepseek", "mistral", "grok", "cohere",
    "perplexity", "groq", "mercury", "pi", "manus", "qwen", "kimi",
    "llama", "glm", "cursor", "notebooklm", "copilot",
]


def get_enabled_nav_keys(module_config):
    """Return the union of nav_keys from all enabled modules."""
    if not module_config or not module_config.get("modules"):
        return set(k for m in MODULE_REGISTRY.values() for k in m["nav_keys"])
    enabled = set()
    for mid, mod in MODULE_REGISTRY.items():
        if mod["always_on"] or (module_config.get("modules") or {}).get(mid, {}).get("enabled", False):
            enabled.update(mod["nav_keys"])
    return enabled


def get_enabled_route_prefixes(module_config):
    """Return all allowed route prefixes from enabled modules."""
    if not module_config or not module_config.get("modules"):
        return set(p for m in MODULE_REGISTRY.values() for p in m["route_prefixes"])
    prefixes = set()
    for mid, mod in MODULE_REGISTRY.items():
        if mod["always_on"] or (module_config.get("modules") or {}).get(mid, {}).get("enabled", False):
            prefixes.update(mod["route_prefixes"])
    return prefixes


def check_module_tier(module_id, user_plan):
    """Check if the user's plan allows this module."""
    mod = MODULE_REGISTRY.get(module_id)
    if not mod:
        return True
    user_tier = PLAN_TIERS.get(user_plan, 0)
    required_tier = PLAN_TIERS.get(mod["min_tier"], 0)
    return user_tier >= required_tier
