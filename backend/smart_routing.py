"""Smart Model Routing — Automatically route prompts to the optimal model by cost/quality.

Routes simple queries to lighter models and complex tasks to premium models.
Users can override with "Force Premium" for critical work.
"""
import logging

logger = logging.getLogger(__name__)

# Model tiers by cost (cheapest first)
MODEL_TIERS = {
    "light": ["groq", "mistral", "deepseek", "llama", "qwen", "gemma"],
    "standard": ["chatgpt", "gemini", "perplexity", "kimi", "glm", "copilot"],
    "premium": ["claude", "grok", "manus", "cursor", "notebooklm"],
}

# Cost per 1K tokens (approximate)
MODEL_COSTS = {
    "groq": 0.0001, "mistral": 0.0002, "deepseek": 0.0003,
    "chatgpt": 0.005, "gemini": 0.003, "perplexity": 0.005,
    "claude": 0.015, "grok": 0.01, "mercury": 0.008,
    "cohere": 0.001, "pi": 0.002, "manus": 0.01,
    "qwen": 0.001, "kimi": 0.003, "llama": 0.0002,
    "glm": 0.002, "cursor": 0.015, "notebooklm": 0.005,
    "copilot": 0.005,
    "gemma": 0.0003,
}

# Task complexity indicators
COMPLEX_INDICATORS = [
    "architect", "design system", "security audit", "refactor", "debug",
    "optimize", "analyze", "complex", "production", "enterprise",
    "critical", "multi-step", "comprehensive",
]
SIMPLE_INDICATORS = [
    "summarize", "translate", "format", "list", "simple",
    "quick", "short", "brief", "one-liner", "typo",
]


def classify_prompt_complexity(prompt: str) -> str:
    """Classify prompt as simple, standard, or complex."""
    lower = prompt.lower()
    
    complex_score = sum(1 for ind in COMPLEX_INDICATORS if ind in lower)
    simple_score = sum(1 for ind in SIMPLE_INDICATORS if ind in lower)
    
    # Length-based heuristic
    if len(prompt) > 2000:
        complex_score += 2
    elif len(prompt) < 100:
        simple_score += 1
    
    if complex_score >= 2:
        return "premium"
    elif simple_score >= 2 or (simple_score > complex_score):
        return "light"
    return "standard"


def get_optimal_model(prompt: str, available_models: list, force_tier: str = None) -> str:
    """Select the optimal model based on prompt complexity and available models."""
    tier = force_tier or classify_prompt_complexity(prompt)
    
    # Try the recommended tier first
    tier_models = MODEL_TIERS.get(tier, MODEL_TIERS["standard"])
    for model in tier_models:
        if model in available_models:
            return model
    
    # Fallback to any available model
    for model in available_models:
        if model in MODEL_COSTS:
            return model
    
    return available_models[0] if available_models else "chatgpt"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for a model call."""
    cost_per_1k = MODEL_COSTS.get(model, 0.005)
    return round((input_tokens + output_tokens) * cost_per_1k / 1000, 6)


def get_dojo_optimal_model(turn_number: int, max_turns: int,
                           available_models: list) -> str:
    """Phase-aware model selection for Dojo sessions.
    Exploration (early)  -> cheap models for broad ideation
    Development (middle) -> standard models for quality work
    Convergence (late)   -> premium models for final precision
    Validation (final)   -> cross-model for independent verification
    """
    progress = turn_number / max(max_turns, 1)
    if progress < 0.2:
        tier = "light"
    elif progress < 0.6:
        tier = "standard"
    elif progress < 0.95:
        tier = "premium"
    else:
        tier = "standard"
    return get_optimal_model("", available_models, force_tier=tier)
