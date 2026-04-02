"""Nexus Configuration — AI Model definitions and constants.
Extracted from server.py to keep the main file manageable.
"""

_BASE_SYSTEM_PROMPT = """participating in a Nexus AI collaboration channel. 

IMPORTANT RULES:
- ONLY respond to the conversation shown below
- Stay focused on the CURRENT topic being discussed
- When writing code: provide COMPLETE, WORKING implementations — never use placeholders, ellipsis, or "// rest of code here"
- Output full files when modifying code. Do not truncate.
- Use proper formatting: wrap code in markdown code blocks with the language specified
- When building software: think through architecture, error handling, and edge cases
- Be collaborative and build on what others said
- Use repo_write_file tool to save code to the repository when appropriate"""

def _make_system_prompt(name, specialty=""):
    prefix = f"You are {name}, "
    if specialty:
        prefix += f"{specialty}, "
    return prefix + _BASE_SYSTEM_PROMPT

AI_MODELS = {
    "chatgpt": {
        "name": "ChatGPT",
        "provider": "openai",
        "model": "gpt-5.4",
        "color": "#10A37F",
        "avatar": "G",
        "mocked": False,
        "requires_user_key": False,
        "auto_collab_max_rounds": 20,
        "system_prompt": _make_system_prompt("ChatGPT")
    },
    "claude": {
        "name": "Claude",
        "provider": "anthropic",
        "model": "claude-opus-4-20250514",
        "color": "#D97757",
        "avatar": "C",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 15,
        "system_prompt": _make_system_prompt("Claude")
    },
    "deepseek": {
        "name": "DeepSeek",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "color": "#4D6BFE",
        "avatar": "D",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 30,
        "system_prompt": _make_system_prompt("DeepSeek")
    },
    "grok": {
        "name": "Grok",
        "provider": "xai",
        "model": "grok-3",
        "color": "#F5F5F5",
        "avatar": "X",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 25,
        "system_prompt": _make_system_prompt("Grok")
    },
    "gemini": {
        "name": "Gemini",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "color": "#4285F4",
        "avatar": "Ge",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 25,
        "system_prompt": _make_system_prompt("Gemini")
    },
    "perplexity": {
        "name": "Perplexity",
        "provider": "perplexity",
        "model": "sonar-pro",
        "color": "#20B2AA",
        "avatar": "P",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 12,
        "system_prompt": _make_system_prompt("Perplexity")
    },
    "mistral": {
        "name": "Mistral",
        "provider": "mistral",
        "model": "mistral-large-latest",
        "color": "#FF7000",
        "avatar": "M",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 25,
        "system_prompt": _make_system_prompt("Mistral")
    },
    "cohere": {
        "name": "Cohere",
        "provider": "cohere",
        "model": "command-a-03-2025",
        "color": "#39594D",
        "avatar": "Co",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 40,
        "system_prompt": _make_system_prompt("Cohere")
    },
    "groq": {
        "name": "Groq",
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "color": "#F55036",
        "avatar": "Gq",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 30,
        "system_prompt": _make_system_prompt("Groq (Llama 3.3 70B)")
    },
    "mercury": {
        "name": "Mercury 2",
        "provider": "inception",
        "model": "mercury-2",
        "color": "#00D4FF",
        "avatar": "Me",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 12,
        "system_prompt": _make_system_prompt("Mercury 2 by Inception Labs")
    },
    "pi": {
        "name": "Pi",
        "provider": "inflection",
        "model": "inflection/inflection-3-pi",
        "color": "#FF6B35",
        "avatar": "Pi",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 12,
        "system_prompt": _make_system_prompt("Pi by Inflection AI")
    },
    "manus": {
        "name": "Manus",
        "provider": "manus",
        "model": "manus-1",
        "color": "#6C5CE7",
        "avatar": "M",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 15,
        "system_prompt": _make_system_prompt("Manus", "an autonomous AI agent by Manus AI")
    },
    "qwen": {
        "name": "Qwen",
        "provider": "alibaba",
        "model": "qwen-plus",
        "color": "#615EFF",
        "avatar": "Qw",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 25,
        "system_prompt": _make_system_prompt("Qwen by Alibaba Cloud")
    },
    "kimi": {
        "name": "Kimi",
        "provider": "moonshot",
        "model": "kimi-k2.5",
        "color": "#000000",
        "avatar": "Ki",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 20,
        "system_prompt": _make_system_prompt("Kimi by Moonshot AI")
    },
    "llama": {
        "name": "Llama",
        "provider": "meta",
        "model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "color": "#0467DF",
        "avatar": "Ll",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 30,
        "system_prompt": _make_system_prompt("Llama by Meta AI")
    },
    "glm": {
        "name": "GLM",
        "provider": "zhipu",
        "model": "glm-4-plus",
        "color": "#3D5AFE",
        "avatar": "GL",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 20,
        "system_prompt": _make_system_prompt("GLM by Zhipu AI")
    },
    "cursor": {
        "name": "Cursor",
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-4",
        "color": "#00E5A0",
        "avatar": "Cu",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 20,
        "system_prompt": _make_system_prompt("Cursor", "an AI-powered coding assistant")
    },
    "notebooklm": {
        "name": "NotebookLM",
        "provider": "openrouter",
        "model": "google/gemini-2.5-pro-preview",
        "color": "#FBBC04",
        "avatar": "NL",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 15,
        "system_prompt": _make_system_prompt("NotebookLM", "a research and knowledge synthesis assistant")
    },
    "copilot": {
        "name": "GitHub Copilot",
        "provider": "openrouter",
        "model": "openai/gpt-4o",
        "color": "#171515",
        "avatar": "GC",
        "mocked": False,
        "requires_user_key": True,
        "auto_collab_max_rounds": 25,
        "system_prompt": _make_system_prompt("GitHub Copilot", "an AI pair programmer")
    },
    "gemma": {
        "name": "Gemma 3", "provider": "google", "model": "gemma-3-27b-it",
        "color": "#4285F4", "avatar": "Gm", "mocked": False, "requires_user_key": True,
        "auto_collab_max_rounds": 20,
        "system_prompt": _make_system_prompt("Gemma 3", "a capable open-weight AI model from Google, specialized in efficient reasoning"),
    },
    "genie3": {
        "name": "Genie 3", "provider": "google", "model": "genie-3",
        "color": "#34A853", "avatar": "G3", "mocked": True, "requires_user_key": True,

# Code Repository prompt extension for AI agents
        "auto_collab_max_rounds": 0, "system_prompt": "",
        "feature_flag": "genie3_world_model", "coming_soon": True,
    },
    "gemini_robotics": {
        "name": "Gemini Robotics", "provider": "google", "model": "gemini-robotics",
        "color": "#EA4335", "avatar": "GR", "mocked": True, "requires_user_key": True,
        "auto_collab_max_rounds": 0, "system_prompt": "",
        "feature_flag": "gemini_robotics", "coming_soon": True,
    },
}
CODE_REPO_PROMPT = """
CODE REPOSITORY: You have access to a shared code repository for this workspace via tools:
- repo_list_files: See all files in the repo
- repo_read_file: Read any file's content by path
- repo_write_file: Create or update a file (commits are tracked with version history)

When writing code for the project, use repo_write_file to save it to the repository.
You can also read existing files with repo_read_file to understand the current codebase before making changes.
When you save code, the system will post "saving to repo" confirmation in the chat."""

SUPPORTED_LANGUAGES_I18N = ("en", "es", "zh", "hi", "ar", "fr", "pt", "ru", "ja", "de")

PROVIDER_PRICING = {
    "anthropic": {"input": 15.0, "output": 75.0},
    "openai": {"input": 10.0, "output": 30.0},
    "gemini": {"input": 1.25, "output": 5.0},
    "deepseek": {"input": 0.14, "output": 0.28},
    "xai": {"input": 3.0, "output": 15.0},
    "cohere": {"input": 2.5, "output": 10.0},
    "mistral": {"input": 2.0, "output": 6.0},
    "groq": {"input": 0.05, "output": 0.10},
    "perplexity": {"input": 1.0, "output": 5.0},
    "openrouter": {"input": 2.0, "output": 8.0},
    "alibaba": {"input": 0.80, "output": 2.0},
    "moonshot": {"input": 1.0, "output": 4.0},
    "meta": {"input": 0.10, "output": 0.30},
    "zhipu": {"input": 0.72, "output": 2.30},
}

FEATURE_FLAGS = {
    "video_generation": {
        "enabled": True,
        "reason": "Video generation via Google Veo 3.1. Requires GOOGLE_AI_KEY.",
    },
    "music_generation": {
        "enabled": True,
        "reason": "Music generation via Google Lyria 3. Requires GOOGLE_AI_KEY.",
    },
    "sfx_generation": {
        "enabled": True,
        "reason": "SFX generation via ElevenLabs Sound Generation API. Requires ELEVENLABS_API_KEY.",
    },
    "turboquant": {
        "enabled": True,
        "reason": "NAVC (Nexus Adaptive Vector Compression) — online vector quantization for KV-cache and vector-search compression.",
    },
    "nexus_helper": {
        "enabled": True,
        "reason": "Nexus Helper — embedded AI assistant for platform guidance and navigation.",
    },
    "smart_inbox": {
        "enabled": False,
        "reason": "Smart Inbox requires provider OAuth configuration. Enable after setting up Gmail/Microsoft credentials in Integration Settings.",
    },
    "agent_dojo": {
        "enabled": True,
        "reason": "Agent Dojo — autonomous agent-to-agent role-playing, mutual training, and synthetic data generation.",
    },
}
