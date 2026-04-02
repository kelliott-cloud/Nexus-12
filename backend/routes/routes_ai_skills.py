"""AI Skills Configuration - Vendor-supported skill libraries per AI model"""
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List, Dict

# Vendor-supported skills per AI model
AI_SKILLS = {
    "claude": {
        "name": "Claude (Anthropic)",
        "skills": [
            {
                "id": "tool_use",
                "name": "Tool Use",
                "description": "Enable Claude to use custom tools and functions you define",
                "category": "functions",
                "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use"
            },
            {
                "id": "computer_use",
                "name": "Computer Use",
                "description": "Allow Claude to interact with computer interfaces (beta)",
                "category": "automation",
                "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/computer-use",
                "beta": True
            },
            {
                "id": "pdf_analysis",
                "name": "PDF/Document Analysis",
                "description": "Extract and analyze content from PDF documents",
                "category": "analysis",
                "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/pdf-support"
            },
            {
                "id": "vision",
                "name": "Vision/Image Analysis",
                "description": "Analyze and understand images",
                "category": "analysis",
                "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/vision"
            }
        ]
    },
    "chatgpt": {
        "name": "ChatGPT (OpenAI)",
        "skills": [
            {
                "id": "code_interpreter",
                "name": "Code Interpreter",
                "description": "Execute Python code, analyze data, create visualizations",
                "category": "code_execution",
                "docs_url": "https://platform.openai.com/docs/assistants/tools/code-interpreter",
                "priority": True
            },
            {
                "id": "dalle_generation",
                "name": "DALL-E Image Generation",
                "description": "Generate images from text descriptions",
                "category": "generation",
                "docs_url": "https://platform.openai.com/docs/guides/images"
            },
            {
                "id": "web_browsing",
                "name": "Web Browsing",
                "description": "Search and browse the web for current information",
                "category": "search",
                "docs_url": "https://platform.openai.com/docs/assistants/tools/web-browser"
            },
            {
                "id": "file_search",
                "name": "File Search & Analysis",
                "description": "Search through and analyze uploaded files",
                "category": "analysis",
                "docs_url": "https://platform.openai.com/docs/assistants/tools/file-search"
            },
            {
                "id": "function_calling",
                "name": "Function Calling",
                "description": "Call custom functions with structured outputs",
                "category": "functions",
                "docs_url": "https://platform.openai.com/docs/guides/function-calling"
            }
        ]
    },
    "gemini": {
        "name": "Gemini (Google)",
        "skills": [
            {
                "id": "code_execution",
                "name": "Code Execution",
                "description": "Execute Python code directly in Gemini",
                "category": "code_execution",
                "docs_url": "https://ai.google.dev/gemini-api/docs/code-execution",
                "priority": True
            },
            {
                "id": "google_search",
                "name": "Google Search Grounding",
                "description": "Ground responses with real-time Google Search results",
                "category": "search",
                "docs_url": "https://ai.google.dev/gemini-api/docs/grounding"
            },
            {
                "id": "function_calling",
                "name": "Function Calling",
                "description": "Define and call custom functions",
                "category": "functions",
                "docs_url": "https://ai.google.dev/gemini-api/docs/function-calling"
            },
            {
                "id": "vision",
                "name": "Vision/Multimodal",
                "description": "Analyze images, videos, and documents",
                "category": "analysis",
                "docs_url": "https://ai.google.dev/gemini-api/docs/vision"
            }
        ]
    },
    "deepseek": {
        "name": "DeepSeek",
        "skills": [
            {
                "id": "code_interpreter",
                "name": "Code Interpreter",
                "description": "Execute code with DeepSeek's reasoning capabilities",
                "category": "code_execution",
                "docs_url": "https://api-docs.deepseek.com/",
                "priority": True
            },
            {
                "id": "math_reasoning",
                "name": "Advanced Math Reasoning",
                "description": "Enhanced mathematical problem-solving with step-by-step reasoning",
                "category": "analysis",
                "docs_url": "https://api-docs.deepseek.com/"
            },
            {
                "id": "function_calling",
                "name": "Function Calling",
                "description": "Call custom functions with JSON schema",
                "category": "functions",
                "docs_url": "https://api-docs.deepseek.com/"
            }
        ]
    },
    "grok": {
        "name": "Grok (xAI)",
        "skills": [
            {
                "id": "web_search",
                "name": "Real-time Web Search",
                "description": "Search the web including real-time X/Twitter data",
                "category": "search",
                "docs_url": "https://docs.x.ai/docs"
            },
            {
                "id": "live_data",
                "name": "Live X/Twitter Data",
                "description": "Access real-time posts, trends, and conversations from X",
                "category": "search",
                "docs_url": "https://docs.x.ai/docs"
            },
            {
                "id": "function_calling",
                "name": "Function Calling",
                "description": "Define custom tools and functions",
                "category": "functions",
                "docs_url": "https://docs.x.ai/docs"
            }
        ]
    },
    "perplexity": {
        "name": "Perplexity",
        "skills": [
            {
                "id": "web_search",
                "name": "Web Search (Built-in)",
                "description": "Real-time web search integrated into every response",
                "category": "search",
                "docs_url": "https://docs.perplexity.ai/",
                "always_enabled": True
            },
            {
                "id": "citations",
                "name": "Source Citations",
                "description": "Automatic citation of sources for all claims",
                "category": "analysis",
                "docs_url": "https://docs.perplexity.ai/",
                "always_enabled": True
            },
            {
                "id": "academic_search",
                "name": "Academic Search",
                "description": "Search academic papers and research databases",
                "category": "search",
                "docs_url": "https://docs.perplexity.ai/"
            }
        ]
    },
    "mistral": {
        "name": "Mistral AI",
        "skills": [
            {
                "id": "function_calling",
                "name": "Function Calling",
                "description": "Native function calling with JSON schema",
                "category": "functions",
                "docs_url": "https://docs.mistral.ai/capabilities/function_calling/"
            },
            {
                "id": "code_generation",
                "name": "Code Generation",
                "description": "Specialized code generation (Codestral model)",
                "category": "code_execution",
                "docs_url": "https://docs.mistral.ai/capabilities/code_generation/",
                "priority": True
            },
            {
                "id": "json_mode",
                "name": "JSON Mode",
                "description": "Guaranteed valid JSON output",
                "category": "functions",
                "docs_url": "https://docs.mistral.ai/capabilities/json_mode/"
            },
            {
                "id": "vision",
                "name": "Vision (Pixtral)",
                "description": "Image understanding with Pixtral model",
                "category": "analysis",
                "docs_url": "https://docs.mistral.ai/capabilities/vision/"
            }
        ]
    },
    "cohere": {
        "name": "Cohere",
        "skills": [
            {
                "id": "rag_search",
                "name": "RAG / Connectors",
                "description": "Retrieval-augmented generation with web and custom connectors",
                "category": "search",
                "docs_url": "https://docs.cohere.com/docs/retrieval-augmented-generation-rag"
            },
            {
                "id": "rerank",
                "name": "Rerank",
                "description": "Rerank search results for better relevance",
                "category": "analysis",
                "docs_url": "https://docs.cohere.com/docs/rerank"
            },
            {
                "id": "tool_use",
                "name": "Tool Use",
                "description": "Define and use custom tools",
                "category": "functions",
                "docs_url": "https://docs.cohere.com/docs/tool-use"
            },
            {
                "id": "embeddings",
                "name": "Embeddings",
                "description": "Generate semantic embeddings for search and clustering",
                "category": "analysis",
                "docs_url": "https://docs.cohere.com/docs/embeddings"
            }
        ]
    },
    "groq": {
        "name": "Groq (Llama)",
        "skills": [
            {
                "id": "function_calling",
                "name": "Function Calling",
                "description": "Llama-native function calling with tools",
                "category": "functions",
                "docs_url": "https://console.groq.com/docs/tool-use"
            },
            {
                "id": "json_mode",
                "name": "JSON Mode",
                "description": "Structured JSON output",
                "category": "functions",
                "docs_url": "https://console.groq.com/docs/text-chat"
            },
            {
                "id": "vision",
                "name": "Vision (Llama 3.2)",
                "description": "Image understanding with Llama 3.2 Vision",
                "category": "analysis",
                "docs_url": "https://console.groq.com/docs/vision"
            }
        ]
    }
}

# Skill categories
SKILL_CATEGORIES = {
    "code_execution": {"name": "Code Execution", "icon": "terminal", "color": "#10B981"},
    "search": {"name": "Search & Browse", "icon": "search", "color": "#3B82F6"},
    "functions": {"name": "Functions & Tools", "icon": "wrench", "color": "#F59E0B"},
    "analysis": {"name": "Analysis", "icon": "chart", "color": "#8B5CF6"},
    "generation": {"name": "Generation", "icon": "sparkles", "color": "#EC4899"},
    "automation": {"name": "Automation", "icon": "bot", "color": "#6366F1"},
}


class UpdateSkillsConfig(BaseModel):
    enabled_skills: Dict[str, List[str]] = Field(
        default={},
        description="Map of AI model key to list of enabled skill IDs"
    )


def register_ai_skills_routes(api_router, db, get_current_user, check_workspace_permission):
    
    @api_router.get("/ai-skills")
    async def get_available_skills(request: Request):
        """Get all available AI skills by model"""
        await get_current_user(request)
        return {
            "skills_by_model": AI_SKILLS,
            "categories": SKILL_CATEGORIES
        }
    
    @api_router.get("/workspaces/{workspace_id}/ai-skills")
    async def get_workspace_skills_config(workspace_id: str, request: Request):
        """Get skills configuration for a workspace"""
        user = await get_current_user(request)
        await check_workspace_permission(db, workspace_id, user["user_id"], "view_workspace")
        
        config = await db.workspace_skills.find_one(
            {"workspace_id": workspace_id},
            {"_id": 0}
        )
        
        if not config:
            # Return default config (code execution skills enabled by default)
            default_enabled = {}
            for model_key, model_info in AI_SKILLS.items():
                default_enabled[model_key] = []
                for skill in model_info["skills"]:
                    # Enable code execution/interpreter by default, or always_enabled skills
                    if skill.get("priority") or skill.get("always_enabled"):
                        default_enabled[model_key].append(skill["id"])
            
            config = {
                "workspace_id": workspace_id,
                "enabled_skills": default_enabled,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "config": config,
            "available_skills": AI_SKILLS,
            "categories": SKILL_CATEGORIES
        }
    
    @api_router.put("/workspaces/{workspace_id}/ai-skills")
    async def update_workspace_skills_config(
        workspace_id: str, 
        data: UpdateSkillsConfig, 
        request: Request
    ):
        """Update skills configuration for a workspace"""
        user = await get_current_user(request)
        await check_workspace_permission(db, workspace_id, user["user_id"], "edit_workspace")
        
        # Validate skill IDs
        for model_key, skill_ids in data.enabled_skills.items():
            if model_key not in AI_SKILLS:
                raise HTTPException(400, f"Invalid AI model: {model_key}")
            
            valid_skill_ids = {s["id"] for s in AI_SKILLS[model_key]["skills"]}
            for skill_id in skill_ids:
                if skill_id not in valid_skill_ids:
                    raise HTTPException(400, f"Invalid skill '{skill_id}' for {model_key}")
        
        # Ensure always_enabled skills stay enabled
        for model_key, model_info in AI_SKILLS.items():
            if model_key not in data.enabled_skills:
                data.enabled_skills[model_key] = []
            for skill in model_info["skills"]:
                if skill.get("always_enabled") and skill["id"] not in data.enabled_skills[model_key]:
                    data.enabled_skills[model_key].append(skill["id"])
        
        await db.workspace_skills.update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    "enabled_skills": data.enabled_skills,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user["user_id"]
                },
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        config = await db.workspace_skills.find_one(
            {"workspace_id": workspace_id},
            {"_id": 0}
        )
        
        return {"status": "updated", "config": config}
    
    @api_router.put("/workspaces/{workspace_id}/ai-skills/{model_key}")
    async def update_model_skills(
        workspace_id: str, 
        model_key: str, 
        request: Request
    ):
        """Toggle skills for a specific AI model"""
        user = await get_current_user(request)
        await check_workspace_permission(db, workspace_id, user["user_id"], "edit_workspace")
        
        if model_key not in AI_SKILLS:
            raise HTTPException(400, f"Invalid AI model: {model_key}")
        
        body = await request.json()
        skill_ids = body.get("skill_ids") or []
        
        # Validate skill IDs
        valid_skill_ids = {s["id"] for s in AI_SKILLS[model_key]["skills"]}
        for skill_id in skill_ids:
            if skill_id not in valid_skill_ids:
                raise HTTPException(400, f"Invalid skill: {skill_id}")
        
        # Ensure always_enabled skills stay enabled
        for skill in AI_SKILLS[model_key]["skills"]:
            if skill.get("always_enabled") and skill["id"] not in skill_ids:
                skill_ids.append(skill["id"])
        
        await db.workspace_skills.update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"enabled_skills.{model_key}": skill_ids,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user["user_id"]
                },
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        return {"status": "updated", "model": model_key, "enabled_skills": skill_ids}
    
    @api_router.get("/workspaces/{workspace_id}/ai-skills/{model_key}")
    async def get_model_skills(workspace_id: str, model_key: str, request: Request):
        """Get enabled skills for a specific AI model in workspace"""
        user = await get_current_user(request)
        await check_workspace_permission(db, workspace_id, user["user_id"], "view_workspace")
        
        if model_key not in AI_SKILLS:
            raise HTTPException(400, f"Invalid AI model: {model_key}")
        
        config = await db.workspace_skills.find_one(
            {"workspace_id": workspace_id},
            {"_id": 0, f"enabled_skills.{model_key}": 1}
        )
        
        enabled = []
        if config and "enabled_skills" in config:
            enabled = config["enabled_skills"].get(model_key, [])
        else:
            # Default: enable priority/code execution skills
            for skill in AI_SKILLS[model_key]["skills"]:
                if skill.get("priority") or skill.get("always_enabled"):
                    enabled.append(skill["id"])
        
        return {
            "model": model_key,
            "model_name": AI_SKILLS[model_key]["name"],
            "enabled_skills": enabled,
            "available_skills": AI_SKILLS[model_key]["skills"]
        }


async def get_enabled_skills_for_model(db, workspace_id: str, model_key: str) -> List[str]:
    """Helper function to get enabled skills for a model in a workspace"""
    if model_key not in AI_SKILLS:
        return []
    
    config = await db.workspace_skills.find_one(
        {"workspace_id": workspace_id},
        {"_id": 0, f"enabled_skills.{model_key}": 1}
    )
    
    if config and "enabled_skills" in config:
        return config["enabled_skills"].get(model_key, [])
    
    # Default: return priority/always_enabled skills
    default_skills = []
    for skill in AI_SKILLS[model_key]["skills"]:
        if skill.get("priority") or skill.get("always_enabled"):
            default_skills.append(skill["id"])
    return default_skills


def get_skill_info(model_key: str, skill_id: str) -> Optional[dict]:
    """Get skill info by model and skill ID"""
    if model_key not in AI_SKILLS:
        return None
    for skill in AI_SKILLS[model_key]["skills"]:
        if skill["id"] == skill_id:
            return skill
    return None
