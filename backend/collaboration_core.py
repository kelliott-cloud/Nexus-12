"""Collaboration Core — AI agent collaboration orchestration.

Extracted from server.py to improve modularity and maintainability.
Contains the core collaboration loop, single-agent execution, and persist collaboration.
"""
import uuid
import time
import asyncio
import logging
import random
from datetime import datetime, timezone

from nexus_config import AI_MODELS, CODE_REPO_PROMPT
from collaboration_engine import (
    active_collaborations, persist_sessions, auto_collab_sessions,
    hard_stop as _hard_stop, pending_batch as _pending_batch, human_priority,
)
from state import state_get, state_set, state_delete

logger = logging.getLogger(__name__)

# Module-level references set by init_collaboration_core() from server.py
_db = None
_ws_manager = None


def init_collaboration_core(db, ws_manager):
    """Initialize module with references from the main app."""
    global _db, _ws_manager
    _db = db
    _ws_manager = ws_manager


async def get_ai_key_for_agent(user_id: str, workspace_id: str, agent_key: str):
    """Get the appropriate API key for an agent.
    Resolution order: Project key → User BYOK → Platform managed key → Env var fallback → Emergent universal fallback"""
    from routes_ai_keys import decrypt_key
    # Get workspace AI config
    workspace = await _db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    ai_config = (workspace.get("ai_config") or {}).get(agent_key, {}) if workspace else {}
    
    key_source = ai_config.get("key_source", "account")
    
    if key_source == "project":
        encrypted = ai_config.get("api_key_encrypted")
        if encrypted:
            try:
                return decrypt_key(encrypted), "project"
            except Exception as e:
                logger.warning(f"Failed to decrypt project key for {agent_key}: {e}")
    
    # Try account-level key (user's personal BYOK)
    user = await _db.users.find_one({"user_id": user_id}, {"_id": 0})
    user_keys = user.get("ai_keys") or {} if user else {}
    encrypted = user_keys.get(agent_key)
    if encrypted:
        try:
            return decrypt_key(encrypted), "account"
        except Exception as e:
            logger.warning(f"Failed to decrypt account key for {agent_key}: {e}")
    
    # Try Nexus Managed Key (platform key with credit deduction)
    try:
        from managed_keys import resolve_platform_key, init_managed_keys, _db as mk_db
        if mk_db is None:
            init_managed_keys(_db)
        managed_key, source = await resolve_platform_key(user_id, agent_key)
        if managed_key:
            logger.info(f"Nexus Managed Key resolved for {agent_key} (user={user_id[:12]})")
            return managed_key, "nexus_managed"
        else:
            logger.debug(f"Managed key not available for {agent_key}: {source}")
    except Exception as e:
        logger.warning(f"Managed key resolution error for {agent_key}: {e}")
    
    # Fallback: env var
    import os
    _AGENT_KEY_MAP = {
        "chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_AI_KEY", "deepseek": "DEEPSEEK_API_KEY",
        "grok": "GROK_API_KEY", "perplexity": "PERPLEXITY_API_KEY",
        "mistral": "MISTRAL_API_KEY", "cohere": "COHERE_API_KEY",
        "groq": "GROQ_API_KEY", "mercury": "MERCURY_API_KEY",
        "pi": "OPENROUTER_API_KEY", "manus": "MANUS_API_KEY",
        "qwen": "QWEN_API_KEY", "kimi": "KIMI_API_KEY",
        "llama": "TOGETHER_API_KEY", "glm": "GLM_API_KEY",
        "cursor": "CURSOR_API_KEY", "notebooklm": "OPENROUTER_API_KEY",
        "copilot": "OPENROUTER_API_KEY",
    }
    env_key = _AGENT_KEY_MAP.get(agent_key)
    if env_key:
        pk = os.environ.get(env_key, "")
        if pk:
            return pk, "platform"

    # No key found
    return None, "none"

async def run_ai_collaboration(channel_id: str, user_id: str, auto_collab_session=None, called_from_persist=False):
    """Run AI collaboration in background - each agent responds sequentially"""
    try:
        from ai_providers import call_ai_direct
        from routes_ai_tools import TOOL_PROMPT, parse_tool_calls, strip_tool_calls, execute_tool

        channel = await _db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            return
        
        workspace_id = channel.get("workspace_id", "")
        
        # Get user's language preference
        user = await _db.users.find_one({"user_id": user_id}, {"_id": 0, "language": 1})
        user_lang = user.get("language", "en") if user else "en"
        
        # Language instruction for AI responses
        lang_instruction = ""
        lang_map = {
            "es": "Spanish", "zh": "Chinese (Simplified)", "hi": "Hindi",
            "ar": "Arabic", "fr": "French", "pt": "Portuguese",
            "ru": "Russian", "ja": "Japanese", "de": "German",
        }
        if user_lang in lang_map:
            lang_instruction = f"\n\nIMPORTANT: You MUST respond entirely in {lang_map[user_lang]}. All your text, code comments, and explanations must be in {lang_map[user_lang]}."
        
        # Load custom Nexus Agents for this workspace
        nexus_agents = {}
        agents_cursor = _db.nexus_agents.find({"workspace_id": workspace_id}, {"_id": 0})
        async for agent in agents_cursor:
            nexus_agents[agent["agent_id"]] = agent

        messages = await _db.messages.find(
            {"channel_id": channel_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(30)
        messages.reverse()

        # Build context using semantic retrieval (hybrid: recent + relevant)
        try:
            from semantic_memory import build_semantic_context
            latest_msg_content = messages[-1].get("content", "") if messages else ""
            context, ctx_msg_count = await build_semantic_context(_db, channel_id, latest_msg_content, max_recent=15, max_relevant=10)
        except Exception as sem_err:
            logger.debug(f"Semantic context failed, using recency: {sem_err}")
            context = "Here is the conversation so far:\n\n"
            max_context_chars = 15000
            for msg in messages:
                sender = msg.get("sender_name", "Unknown")
                content = msg.get("content", "")
                if len(content) > 2000:
                    content = content[:2000] + "... [truncated]"
                entry = f"[{sender}]: {content}\n\n"
                if len(context) + len(entry) > max_context_chars:
                    context += "[... earlier messages truncated for context limit]\n\n"
                    break
                context += entry

        # Determine which agents to activate based on @mentions
        last_human_msg = None
        for msg in reversed(messages):
            if msg.get("sender_type") == "human":
                last_human_msg = msg
                break

        mention_data = last_human_msg.get("mentions") or {} if last_human_msg else {}
        mentioned_agents = mention_data.get("mentioned_agents") or []
        mention_everyone = mention_data.get("mention_everyone", False)
        has_mentions = mention_data.get("has_mentions", False)

        # Determine active agent list
        all_channel_agents = channel.get("ai_agents") or []
        if has_mentions and not mention_everyone:
            # Only respond with specifically mentioned agents
            target_agents = [a for a in all_channel_agents if a in mentioned_agents]
        else:
            # @everyone or no mentions → all agents respond
            target_agents = all_channel_agents

        # Filter out disabled agents
        disabled_agents = channel.get("disabled_agents") or []
        if disabled_agents:
            target_agents = [a for a in target_agents if a not in disabled_agents]

        # --- PRE-FETCH SHARED CONTEXT (once for all agents) ---
        kb_context = ""
        try:
            kb_entries = await _db.workspace_memory.find(
                {"workspace_id": workspace_id}, {"_id": 0, "key": 1, "value": 1, "category": 1}
            ).sort("updated_at", -1).limit(10).to_list(10)
            if kb_entries:
                kb_lines = [f"- {e['key']}: {e['value'][:300]}" for e in kb_entries]
                kb_context = "\n\n[KNOWLEDGE BASE] The following project context is available:\n" + "\n".join(kb_lines) + "\nUse this context to inform your response but don't reference it unless directly relevant."
        except Exception as kb_err:
            logger.warning(f"KB injection failed: {kb_err}")

        repo_context = ""
        try:
            repo_files = await _db.repo_files.find(
                {"workspace_id": workspace_id, "is_deleted": {"$ne": True}},
                {"_id": 0, "path": 1, "is_folder": 1, "language": 1, "size": 1, "version": 1}
            ).sort("path", 1).to_list(50)
            if repo_files:
                tree_lines = []
                for rf in repo_files:
                    if rf.get("is_folder"):
                        tree_lines.append(f"  {rf['path']}/")
                    else:
                        tree_lines.append(f"  {rf['path']} [{rf.get('language','')}] v{rf.get('version',1)}")
                repo_context = f"\n\n[CODE REPOSITORY] The workspace has {len(repo_files)} files:\n" + "\n".join(tree_lines[:30])
                repo_context += "\n\nUse repo_list_files and repo_read_file tools to interact with these files."
        except Exception as repo_ctx_err:
            logger.warning(f"Repo context injection failed: {repo_ctx_err}")

        # --- RUN AGENTS IN PARALLEL ---
        async def run_single_agent(agent_key, context_snapshot, ws_id=None, ch_id=None):
            """Run a single agent and return its response"""
            # Explicit datetime reference to prevent Python 3.12+ scoping issues
            from datetime import datetime, timezone
            # Use passed params instead of closure to avoid scope issues
            _workspace_id = ws_id or workspace_id
            _channel_id = ch_id or channel_id
            # Resolve workspace owner for context injection and reporting
            _ws_doc = await _db.workspaces.find_one({"workspace_id": _workspace_id}, {"_id": 0, "owner_id": 1, "org_id": 1})
            _owner_id = _ws_doc.get("owner_id", user_id) if _ws_doc else user_id
            round_num = (auto_collab_session.get("agent_rounds") or {}).get(agent_key, 0) if auto_collab_session else 0
            # Check auto-collab per-agent rate limits
            if auto_collab_session:
                agent_rounds = auto_collab_session.get("agent_rounds") or {}
                current_rounds = agent_rounds.get(agent_key, 0)
                max_rounds = AI_MODELS.get(agent_key, {}).get("auto_collab_max_rounds", 5)
                if current_rounds >= max_rounds:
                    logger.info(f"Auto-collab: {agent_key} reached max {max_rounds} rounds, skipping")
                    return
                if "agent_rounds" not in auto_collab_session:
                    auto_collab_session["agent_rounds"] = {}
                auto_collab_session["agent_rounds"][agent_key] = current_rounds + 1

            # Check if it's a custom Nexus Agent or a built-in model
            is_nexus_agent = agent_key.startswith("nxa_")
            
            if is_nexus_agent:
                if agent_key not in nexus_agents:
                    return
                nexus_agent = nexus_agents[agent_key]
                base_model_key = nexus_agent["base_model"]
                if base_model_key not in AI_MODELS:
                    return
                base_model_config = AI_MODELS[base_model_key]
                
                model_config = {
                    "name": nexus_agent["name"],
                    "provider": base_model_config["provider"],
                    "model": base_model_config["model"],
                    "color": nexus_agent["color"],
                    "avatar": nexus_agent["avatar"],
                    "system_prompt": nexus_agent["system_prompt"],
                    "requires_user_key": base_model_config.get("requires_user_key", False),
                }

                # === SKILL-AWARE PROMPT ASSEMBLY (for Nexus Agents with skills) ===
                if nexus_agent.get("skills"):
                    try:
                        from agent_prompt_builder import build_agent_prompt
                        enriched_prompt = await build_agent_prompt(_db, nexus_agent, _workspace_id, _channel_id)
                        model_config["system_prompt"] = enriched_prompt
                    except Exception as skill_err:
                        logger.debug(f"Skill prompt assembly failed for {agent_key}: {skill_err}")

                # Apply channel-level model override for nexus agents too
                channel_agent_models = channel.get("agent_models") or {}
                if agent_key in channel_agent_models:
                    model_config["model"] = channel_agent_models[agent_key]
                effective_agent_key = base_model_key
            else:
                if agent_key not in AI_MODELS:
                    return
                model_config = {**AI_MODELS[agent_key]}  # Copy so we can override
                effective_agent_key = agent_key
            
            # Apply channel-level model override
            channel_agent_models = channel.get("agent_models") or {}
            if agent_key in channel_agent_models:
                model_config["model"] = channel_agent_models[agent_key]
            elif effective_agent_key in channel_agent_models:
                model_config["model"] = channel_agent_models[effective_agent_key]
            
            # Get the appropriate API key for this agent's base model
            user_api_key, key_source = await get_ai_key_for_agent(user_id, _workspace_id, effective_agent_key)

            # Smart routing: log complexity classification
            try:
                from smart_routing import classify_prompt_complexity, estimate_cost
                last_msg = messages[-1].get("content", "") if messages else ""
                complexity = classify_prompt_complexity(last_msg)
                estimate_cost(effective_agent_key, 2000, 1000)
                if complexity == "light" and effective_agent_key in ("claude", "grok", "manus"):
                    logger.info(f"Smart routing: {effective_agent_key} handling '{complexity}' prompt — consider lighter model")
            except Exception as _e:
                logger.debug(f"Silent exception: {_e}")

            # Budget enforcement — check before making AI call
            try:
                from managed_keys import should_bypass_budget
                bypass_local_budget = await should_bypass_budget(user_id)
                budget_doc = await _db.workspace_budgets.find_one({"workspace_id": _workspace_id}, {"_id": 0, "monthly_cap_usd": 1})
                if budget_doc and budget_doc.get("monthly_cap_usd") and not bypass_local_budget:
                    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    monthly_events = await _db.reporting_events.find(
                        {"workspace_id": _workspace_id, "created_at": {"$gte": month_start.isoformat()}, "event_type": "ai_call"},
                        {"_id": 0, "estimated_cost_usd": 1}
                    ).limit(1000).to_list(500)
                    monthly_spend = sum(e.get("estimated_cost_usd", 0) for e in monthly_events)
                    if monthly_spend >= budget_doc["monthly_cap_usd"]:
                        logger.warning(f"Budget exceeded for {_workspace_id}: ${monthly_spend:.2f} >= ${budget_doc['monthly_cap_usd']}")
                        await _db.messages.insert_one({
                            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                            "channel_id": _channel_id,
                            "sender_type": "system", "sender_id": "system", "sender_name": "System",
                            "content": f"_Monthly AI budget (${budget_doc['monthly_cap_usd']}) has been reached. {model_config['name']} paused._",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        })
                        return
            except Exception as budget_err:
                logger.debug(f"Budget check failed: {budget_err}")

            # Nexus AI scope budgets — workspace overrides org overrides platform
            try:
                from managed_keys import check_usage_budget, estimate_ai_cost_usd, emit_budget_alert
                preview_cost = estimate_ai_cost_usd(effective_agent_key, max(len(context_snapshot) // 4, 1), 1000)
                scope_budget = await check_usage_budget(
                    effective_agent_key,
                    preview_cost,
                    workspace_id=_workspace_id,
                    org_id=_ws_doc.get("org_id") if _ws_doc else None,
                    user_id=user_id,
                )
                if scope_budget.get("blocked"):
                    scope_name = (scope_budget.get("scope_type") or "platform").capitalize()
                    scope_message = f"{scope_name} Nexus AI budget reached for {effective_agent_key}."
                    await emit_budget_alert(
                        effective_agent_key,
                        scope_budget.get("scope_type") or "platform",
                        scope_budget.get("scope_id") or "platform",
                        "blocked",
                        scope_budget.get("projected_spend_usd", preview_cost),
                        scope_budget.get("hard_cap_usd"),
                        user_id=user_id,
                        workspace_id=_workspace_id,
                        org_id=_ws_doc.get("org_id") if _ws_doc else None,
                        message=scope_message,
                    )
                    await _db.messages.insert_one({
                        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                        "channel_id": _channel_id,
                        "sender_type": "system",
                        "sender_id": "system",
                        "sender_name": "System",
                        "content": f"_{model_config['name']} paused: {scope_name} Nexus AI budget reached for {effective_agent_key}. Increase the budget in Settings → Nexus AI, or use your own provider key in Settings → AI Keys._",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    return
            except Exception as budget_scope_err:
                logger.debug(f"Scope budget check failed: {budget_scope_err}")
            
            # Skip agents that require user keys if no key is provided
            if model_config.get("requires_user_key") and not user_api_key:
                logger.info(f"Skipping {agent_key} - requires user API key")
                # Only post the "requires key" message for one-off collaborations, not persist/auto-collab
                if not called_from_persist and not auto_collab_session:
                    skip_message = {
                        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                        "channel_id": _channel_id,
                        "sender_type": "system",
                        "sender_id": "system",
                        "sender_name": "System",
                        "content": f"_{model_config['name']} requires an API key to participate. Add your key in Settings to enable this agent._",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await _db.messages.insert_one(skip_message)
                return
            
            await state_set("collab:active", f"{_channel_id}_{agent_key}", "thinking")

            try:
                # Build prompt using shared context snapshot
                user_prompt = f"""=== CURRENT CONVERSATION (respond ONLY to this) ===
{context_snapshot}
=== END OF CONVERSATION ===

Your task: Contribute a helpful, detailed response to the conversation above. 
- Stay on topic and build on what others have said
- When asked to write code: provide COMPLETE, WORKING implementations with no placeholders
- Always use markdown code blocks with the language tag (```python, ```javascript, etc.)
- Think through edge cases and error handling
- If the request involves multiple files, address each one fully
- Use repo_write_file tool to save code when building a project"""
                
                start_time = time.time()
                
                if not user_api_key:
                    logger.info(f"Skipping {agent_key} - no API key provided")
                    if not called_from_persist and not auto_collab_session:
                        skip_message = {
                            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                            "channel_id": _channel_id,
                            "sender_type": "system",
                            "sender_id": "system",
                            "sender_name": "System",
                            "content": f"_{model_config['name']} requires an API key to participate. Add your key in Settings to enable this agent._",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await _db.messages.insert_one(skip_message)
                    return
                
                # Include tool prompt + pre-fetched context
                from platform_capabilities import PLATFORM_CAPABILITIES
                from dedup_engine import DEDUP_PROMPT_INJECTION
                from confidence_scoring import CONFIDENCE_PROMPT
                full_system_prompt = model_config["system_prompt"] + lang_instruction + TOOL_PROMPT + CODE_REPO_PROMPT + PLATFORM_CAPABILITIES + DEDUP_PROMPT_INJECTION + CONFIDENCE_PROMPT

                # === COORDINATION PROTOCOL INJECTION ===
                coordination_context = ""
                try:
                    # Load workspace memory — what other agents are working on
                    agent_states = await _db.workspace_memory.find(
                        {"workspace_id": _workspace_id, "namespace": "agent_state"},
                        {"_id": 0, "key": 1, "value": 1, "updated_at": 1}
                    ).to_list(15)
                    
                    # Load active work queue
                    my_assignments = await _db.work_queue.find(
                        {"workspace_id": _workspace_id, "assigned_to": agent_key, "status": {"$in": ["pending", "in_progress"]}},
                        {"_id": 0, "title": 1, "description": 1, "project_id": 1, "status": 1}
                    ).to_list(10)
                    
                    # Load existing projects for dedup awareness
                    existing_projects = await _db.projects.find(
                        {"workspace_id": _workspace_id},
                        {"_id": 0, "project_id": 1, "name": 1, "status": 1}
                    ).to_list(30)
                    
                    coordination_context = "\n\n=== COORDINATION PROTOCOL (MANDATORY) ===\n"
                    coordination_context += "CRITICAL RULES — violating these causes duplicate work:\n"
                    coordination_context += "1. NEVER create a new project if one with a similar name exists below\n"
                    coordination_context += "2. ALWAYS use the existing project_id when adding tasks to a project\n"
                    coordination_context += "3. CHECK your assignments before starting any work\n"
                    coordination_context += "4. SAVE your current state to workspace memory after completing work\n"
                    coordination_context += "5. If a TPM has assigned you specific work, do ONLY that work\n"
                    coordination_context += "6. If you are NOT assigned work and a TPM exists, WAIT for assignment\n\n"
                    
                    if existing_projects:
                        coordination_context += "EXISTING PROJECTS (use these IDs, do NOT create duplicates):\n"
                        for p in existing_projects:
                            coordination_context += f"  - {p['name']} (ID: {p['project_id']}, status: {p.get('status','active')})\n"
                        coordination_context += "\n"
                    
                    if my_assignments:
                        coordination_context += f"YOUR ASSIGNED WORK ({agent_key}):\n"
                        for a in my_assignments:
                            coordination_context += f"  - [{a['status']}] {a['title']}"
                            if a.get('project_id'):
                                coordination_context += f" (project: {a['project_id']})"
                            coordination_context += "\n"
                        coordination_context += "Focus on these assignments. Do not start unassigned work.\n\n"
                    
                    # === TPM QUEUE: Load latest directives from TPM ===
                    tpm_directives = await _db.tpm_queue.find(
                        {"workspace_id": _workspace_id, "status": "active",
                         "$or": [{"target_agent": agent_key}, {"target_agent": "all"}]},
                        {"_id": 0}
                    ).sort("created_at", -1).to_list(5)
                    
                    if tpm_directives:
                        coordination_context += "=== TPM DIRECTIVES (YOU MUST FOLLOW THESE) ===\n"
                        for d in tpm_directives:
                            coordination_context += f"  [{d.get('priority','normal').upper()}] {d.get('directive','')}\n"
                            if d.get('context'):
                                coordination_context += f"    Context: {d['context'][:200]}\n"
                        coordination_context += "These are direct orders from the TPM. Follow them before doing anything else.\n"
                        coordination_context += "If you need clarification, use the ask_tpm tool.\n"
                        coordination_context += "=== END TPM DIRECTIVES ===\n\n"
                    
                    # === CHECK: Has TPM posted since my last message? If so, reorient ===
                    ws_data = await _db.workspaces.find_one({"workspace_id": _workspace_id}, {"_id": 0, "tpm_agent_id": 1})
                    ws_tpm_id = (ws_data or {}).get("tpm_agent_id")
                    if ws_tpm_id and ws_tpm_id != agent_key:
                        tpm_agent_doc = await _db.nexus_agents.find_one({"agent_id": ws_tpm_id}, {"_id": 0, "name": 1, "base_model": 1})
                        tpm_name = (tpm_agent_doc or {}).get("name", ws_tpm_id)
                        # Get TPM's latest message in this channel
                        latest_tpm_msg = await _db.messages.find_one(
                            {"channel_id": _channel_id, "agent": (tpm_agent_doc or {}).get("base_model", ""),
                             "sender_type": "ai"},
                            {"_id": 0, "content": 1, "created_at": 1}
                        )
                        if latest_tpm_msg:
                            coordination_context += f"=== LATEST TPM MESSAGE FROM {tpm_name.upper()} ===\n"
                            coordination_context += f"{str(latest_tpm_msg.get('content',''))[:500]}\n"
                            coordination_context += "REORIENT: Read this TPM message carefully. Adjust your current work to align with the TPM's direction.\n"
                            coordination_context += "=== END TPM MESSAGE ===\n\n"
                    
                    if agent_states:
                        coordination_context += "OTHER AGENTS' CURRENT STATE:\n"
                        for s in agent_states:
                            if s["key"] != f"state:{agent_key}":
                                coordination_context += f"  - {s['key']}: {str(s.get('value',''))[:150]}\n"
                        coordination_context += "\n"
                    
                    coordination_context += "=== END COORDINATION PROTOCOL ===\n"
                    
                    # ENFORCEMENT: If TPM exists and agent has NO assignments, restrict output
                    has_tpm = any(a.get("category") == "tpm" or "tpm" in (a.get("name") or "").lower() 
                                 for a in await _db.nexus_agents.find({"workspace_id": _workspace_id}, {"_id": 0, "name": 1, "category": 1}).to_list(20))
                    total_queue = await _db.work_queue.count_documents({"workspace_id": _workspace_id, "status": {"$in": ["pending", "in_progress"]}})
                    
                    if has_tpm and total_queue > 0 and not my_assignments:
                        # Check if current agent is the TPM
                        current_agent_doc = await _db.nexus_agents.find_one({"workspace_id": _workspace_id, "base_model": agent_key}, {"_id": 0, "category": 1})
                        if not current_agent_doc or current_agent_doc.get("category") != "tpm":
                            coordination_context += "\n*** BLOCKED: A TPM is managing this workspace and you have NO assigned work items. "
                            coordination_context += "You MUST wait for the TPM to assign you work. "
                            coordination_context += "Respond ONLY with: 'Waiting for TPM assignment. I have no current tasks.' ***\n"
                    
                except Exception as coord_err:
                    logger.debug(f"Coordination context failed: {coord_err}")
                
                full_system_prompt += coordination_context

                # === DESKTOP BRIDGE INJECTION ===
                try:
                    from mcp_bridge.routes import _bridge_connections
                    if _owner_id in _bridge_connections:
                        from mcp_bridge.tools import BRIDGE_TOOL_PROMPT
                        full_system_prompt += BRIDGE_TOOL_PROMPT
                except Exception as _e:
                    logger.debug(f"Silent exception: {_e}")

                # === AGENT MEMORY INJECTION ===
                try:
                    agent_mems = await _db.agent_memory.find(
                        {"workspace_id": _workspace_id, "$or": [
                            {"scope": "organization"},
                            {"scope": "channel", "scope_id": _channel_id},
                        ]},
                        {"_id": 0, "content": 1, "category": 1, "scope": 1}
                    ).limit(15).to_list(15)
                    if agent_mems:
                        full_system_prompt += "\n\n=== PERSISTENT MEMORY ===\nFacts you should remember:\n"
                        for m in agent_mems:
                            full_system_prompt += f"- [{m.get('scope','?')}/{m.get('category','fact')}] {m['content']}\n"
                        full_system_prompt += "=== END MEMORY ===\n"
                except Exception as mem_err:
                    logger.warning(f"Agent memory injection failed: {mem_err}")

                # === AGENT DASHBOARD CONTEXT BLOCK ===
                try:
                    from agent_context_builder import build_agent_context_block
                    ctx_block = await build_agent_context_block(
                        _db, agent_key, model_config.get("name", agent_key),
                        _workspace_id, _channel_id, _owner_id, round_num
                    )
                    if ctx_block:
                        full_system_prompt += ctx_block
                except Exception as ctx_err:
                    logger.debug(f"Context block injection failed: {ctx_err}")

                # === CONVERSATION SUMMARIES ===
                try:
                    from conversation_summarizer import build_summary_context
                    sum_ctx = await build_summary_context(_db, _channel_id)
                    if sum_ctx:
                        full_system_prompt += sum_ctx
                except Exception as sum_err:
                    logger.warning(f"Summary injection failed: {sum_err}")

                # === EXTENDED TOOLS PROMPT ===
                full_system_prompt += """
ADDITIONAL TOOLS AVAILABLE:
- web_search(query) — Search the internet for information
- generate_image(prompt) — Generate an image from a text description  
- ask_human(question, options) — Ask the user a structured question with options
- read_file(file_id) — Read the text content of an uploaded file
- log_decision(decision, alternatives, rationale) — Log a project decision
- query_decisions(query) — Search previous decisions
- search_channels(query) — Search across all workspace channels
- send_alert(message, severity) — Send an alert notification (info/warning/critical)
- branch_conversation(branch_name) — Fork the conversation to explore alternatives

When responding, include a confidence indicator at the end of your message:
[CONFIDENCE: X%] where X is your self-assessed confidence (0-100).
"""

                # After each response, save agent state to workspace memory
                async def _save_agent_state(agent_key, summary):
                    try:
                        await _db.workspace_memory.update_one(
                            {"workspace_id": _workspace_id, "key": f"state:{agent_key}"},
                            {"$set": {
                                "workspace_id": _workspace_id,
                                "key": f"state:{agent_key}",
                                "value": summary[:300],
                                "namespace": "agent_state",
                                "agent_key": agent_key,
                                "updated_by": agent_key,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }},
                            upsert=True,
                        )
                    except Exception as _e:
                        logger.debug(f"Silent exception: {_e}")
                if kb_context:
                    full_system_prompt += kb_context
                if repo_context:
                    full_system_prompt += repo_context
                
                # Inject TPM/Architect/Browser Operator role instructions
                channel_roles = channel.get("channel_roles") or {}
                tpm_key = channel_roles.get("tpm")
                architect_key = channel_roles.get("architect")
                browser_op_key = channel_roles.get("browser_operator")
                
                if agent_key == tpm_key:
                    full_system_prompt += "\n\n=== YOUR ROLE: TECHNICAL PROJECT MANAGER (TPM) ===\nYou are the TPM for this channel. You are responsible for:\n- Setting the direction and priorities for all agents\n- Breaking down work into clear tasks and assigning them\n- Specifying the order of execution\n- Reviewing progress and coordinating between agents\nAll other agents MUST follow your instructions. You speak FIRST each round.\nThe only exception: the Architect agent may override you on design/architecture decisions.\n=== END TPM ROLE ===\n"
                elif agent_key == architect_key:
                    full_system_prompt += "\n\n=== YOUR ROLE: ARCHITECT ===\nYou are the Architect for this channel. You have supreme authority on:\n- System design and architecture decisions\n- Technology choices and patterns\n- Code structure and organization\nYou can OVERRULE any other agent (including the TPM) on design decisions.\nDefer to the TPM on project management, scheduling, and task prioritization.\n=== END ARCHITECT ROLE ===\n"
                elif tpm_key:
                    tpm_name = AI_MODELS.get(tpm_key, {}).get("name", tpm_key)
                    full_system_prompt += f"\n\n[CHANNEL HIERARCHY] {tpm_name} is the TPM (Technical Project Manager) for this channel. You MUST follow their direction on tasks, priorities, and execution order. Do what the TPM tells you to do."
                    if architect_key:
                        arch_name = AI_MODELS.get(architect_key, {}).get("name", architect_key)
                        full_system_prompt += f" {arch_name} is the Architect and has authority on design decisions."
                    full_system_prompt += "\n"
                
                # Browser Operator role
                if agent_key == browser_op_key:
                    full_system_prompt += "\n\n=== YOUR ROLE: BROWSER OPERATOR ===\nYou are the designated Browser Operator for this channel. You control the Nexus Browser.\nUse browser_navigate, browser_click, browser_type, browser_read tools to interact with web pages.\nIf you encounter CAPTCHAs, login screens, or anything you cannot handle, use browser_request_help to ask the human.\nAlways describe what you see on the page after each action.\n=== END BROWSER OPERATOR ROLE ===\n"
                elif browser_op_key:
                    bop_name = AI_MODELS.get(browser_op_key, {}).get("name", browser_op_key)
                    full_system_prompt += f"\n[BROWSER] {bop_name} is the Browser Operator. Only they should use browser tools. If you need something from the web, ask {bop_name} to look it up.\n"
                
                # QA role (can be multiple agents)
                qa_agents = channel_roles.get("qa") or []
                if agent_key in qa_agents:
                    full_system_prompt += "\n\n=== YOUR ROLE: QA ENGINEER ===\nYou are a QA agent for this channel. Your responsibilities:\n- Review ALL code and outputs from other agents for correctness, bugs, and edge cases\n- Write test cases and validation criteria\n- Challenge assumptions and find failure modes\n- Do NOT write production code — only tests, reviews, and bug reports\n- Use create_task tool to file bugs with priority 'high' and status 'todo'\n- When reviewing code, check: error handling, input validation, security, performance\n- Be thorough — if you find no issues, explicitly say the code passes QA\n=== END QA ROLE ===\n"
                elif qa_agents:
                    qa_names = [AI_MODELS.get(a, {}).get("name", a) for a in qa_agents]
                    full_system_prompt += f"\n[QA] {', '.join(qa_names)} {'are' if len(qa_names) > 1 else 'is'} the QA engineer(s). They will review your code. Do NOT do QA work — focus on your assigned role.\n"
                
                # Security role
                security_key = channel_roles.get("security")
                if agent_key == security_key:
                    full_system_prompt += "\n\n=== YOUR ROLE: SECURITY REVIEWER ===\nYou are the Security agent for this channel. Your responsibilities:\n- Examine ALL designs, code, and architecture for security vulnerabilities\n- Check for: XSS, SQL injection, auth bypass, data exposure, insecure defaults, missing encryption\n- Review API endpoints for proper authentication and authorization\n- Flag any sensitive data handling issues (PII, credentials, tokens)\n- Do NOT write production code — only security reviews, threat assessments, and remediation recommendations\n- Use create_task tool to file security issues with priority 'critical'\n- Reference OWASP Top 10 when applicable\n=== END SECURITY ROLE ===\n"
                elif security_key:
                    sec_name = AI_MODELS.get(security_key, {}).get("name", security_key)
                    full_system_prompt += f"\n[SECURITY] {sec_name} is the Security Reviewer. They will assess your work for vulnerabilities.\n"
                
                # TPM restrictions — HARD enforcement: no code output, only coordination
                if agent_key == tpm_key:
                    # Also check if agent is TPM by category
                    _is_tpm = True
                elif not tpm_key:
                    _tpm_check = await _db.nexus_agents.find_one({"workspace_id": _workspace_id, "base_model": agent_key, "category": "tpm"}, {"_id": 0})
                    _is_tpm = bool(_tpm_check)
                else:
                    _is_tpm = False
                
                if _is_tpm:
                    full_system_prompt += """

=== ABSOLUTE TPM RESTRICTIONS (VIOLATION = IMMEDIATE STOP) ===
You are the TPM. You MUST NOT:
- Write ANY code (no Python, JavaScript, HTML, CSS, SQL, shell, or ANY programming language)
- Write code blocks (no ``` blocks of any kind)
- Implement solutions yourself
- Fix bugs yourself — assign them to the correct agent
- Do ANY work that another agent should do

You MUST ONLY:
- Create and assign tasks using create_task tool (assign to specific agents)
- Update task statuses and priorities
- Create project milestones and track progress
- Post directives to the TPM queue for agents to follow
- Review agent work and provide feedback (text only, no code)
- Resolve conflicts between agents
- Ensure no duplicate work — check existing tasks before creating new ones
- Direct questions to the appropriate agent by name

When you need an agent to do something, use create_work_item to assign it.
When reviewing code, provide text feedback only. Never rewrite code.
=== END TPM RESTRICTIONS ===
"""
                
                # Inject current browser state if session is active
                try:
                    from routes_nexus_browser import get_session_info, get_page_text
                    browser_info = get_session_info(_channel_id)
                    if browser_info:
                        full_system_prompt += f"\n[BROWSER STATE] Nexus Browser is open at: {browser_info.get('current_url', '?')}"
                        if browser_info.get("help_requested"):
                            full_system_prompt += f"\n  HELP REQUESTED: {browser_info.get('help_message', '')}"
                        if agent_key == browser_op_key:
                            # Give the browser operator the page text for context
                            page = await get_page_text(_channel_id, max_chars=2000)
                            if page and "error" not in page:
                                full_system_prompt += f"\n  Page title: {page.get('title', '?')}\n  Page content:\n{page.get('text', '')[:1500]}"
                            full_system_prompt += "\n  Use browser_get_elements to see clickable elements, browser_read for full text."
                        full_system_prompt += "\n"
                except Exception as _exc:
                    logger.debug(f"Non-critical error: {_exc}")
                
                # Inject Context Ledger awareness — prevents repeated responses
                try:
                    from routes_context_ledger import get_agent_prior_context, build_context_awareness_prompt
                    prior_ctx = await get_agent_prior_context(_db, _channel_id, agent_key, limit=5)
                    if prior_ctx:
                        ctx_prompt = build_context_awareness_prompt(prior_ctx, model_config["name"])
                        full_system_prompt += ctx_prompt
                except Exception as ctx_err:
                    logger.warning(f"Context ledger injection failed: {ctx_err}")

                # Inject active directive rules into system prompt
                # CRITICAL: Rules are injected BEFORE the main prompt for maximum compliance
                directive_rules_prefix = ""
                directive_rules_suffix = ""
                active_dir = None
                try:
                    active_dir = await _db.directives.find_one(
                        {"workspace_id": _workspace_id, "is_active": True},
                        {"_id": 0, "project_name": 1, "agents": 1, "universal_rules": 1, "goal": 1}
                    )
                    if active_dir:
                        # Build rules prefix (goes BEFORE everything else)
                        rules = active_dir.get("universal_rules") or {}
                        prohibited = rules.get("prohibited_patterns") or []
                        if prohibited:
                            directive_rules_prefix = "\n=== MANDATORY RULES (NEVER VIOLATE) ===\n"
                            for pattern in prohibited:
                                directive_rules_prefix += f"STRICTLY PROHIBITED: You must NEVER output '{pattern}'. If you include this pattern, your response will be rejected.\n"
                            directive_rules_prefix += "=== END MANDATORY RULES ===\n\n"
                        
                        if rules.get("additive_only"):
                            directive_rules_prefix += "RULE: Do NOT delete or remove existing code. Only add new code.\n"
                        if rules.get("full_file_context"):
                            directive_rules_prefix += "RULE: Always output the COMPLETE file when modifying code, never use placeholders.\n"

                        # Build directive context suffix
                        directive_rules_suffix = f"\n\n[ACTIVE DIRECTIVE: {active_dir.get('project_name', '')}]"
                        if active_dir.get("goal"):
                            directive_rules_suffix += f"\nGoal: {active_dir['goal']}"
                        # Agent-specific rules
                        agent_cfg = (active_dir.get("agents") or {}).get(agent_key, {})
                        if agent_cfg:
                            if agent_cfg.get("role"):
                                directive_rules_suffix += f"\nYour role: {agent_cfg['role']}"
                            for constraint in agent_cfg.get("prompt_constraints") or []:
                                directive_rules_suffix += f"\nConstraint: {constraint}"

                        # Prepend rules and append directive context
                        full_system_prompt = directive_rules_prefix + full_system_prompt + directive_rules_suffix
                except Exception as dir_err:
                    logger.warning(f"Directive injection failed: {dir_err}")
                
                # Use direct API call with user's key
                # CHECK: Human priority — pause if human sent a message
                hp = await state_get("collab:priority", _channel_id)
                if hp and hp.get("pause_requested") and not hp.get("processed"):
                    logger.info(f"Agent {agent_key} pausing for human priority in {_channel_id}")
                    return  # Yield to human message
                
                logger.info(f"Using {key_source} key for {agent_key}")
                response_text = await call_ai_direct(
                    effective_agent_key,
                    user_api_key, 
                    full_system_prompt, 
                    user_prompt,
                    model_override=model_config.get("model"),
                    workspace_id=_workspace_id,
                    db=_db,
                    channel_id=_channel_id,
                )
                
                response_time_ms = int((time.time() - start_time) * 1000)

                # Parse and execute any tool calls in the response
                tool_calls = parse_tool_calls(response_text)
                visible_text = strip_tool_calls(response_text) if tool_calls else response_text
                
                # Validate response against prohibited patterns
                violations = []
                try:
                    if active_dir:
                        d_rules = active_dir.get("universal_rules") or {}
                        for pattern in d_rules.get("prohibited_patterns") or []:
                            if pattern.lower() in visible_text.lower():
                                violations.append(pattern)
                    if violations:
                        violation_warning = f"\n\n_[Directive Violation: Response contained prohibited pattern(s): {', '.join(violations)}]_"
                        visible_text += violation_warning
                        logger.warning(f"Agent {agent_key} violated prohibited patterns: {violations}")
                except Exception as _exc:
                    logger.debug(f"Non-critical error: {_exc}")

                # === TPM CODE ENFORCEMENT: Strip code blocks from TPM responses ===
                is_tpm_agent = (agent_key == (channel.get("channel_roles") or {}).get("tpm"))
                if not is_tpm_agent:
                    _tpm_cat_check = await _db.nexus_agents.find_one({"workspace_id": _workspace_id, "base_model": agent_key, "category": "tpm"}, {"_id": 0})
                    if _tpm_cat_check:
                        is_tpm_agent = True
                if not is_tpm_agent:
                    ws_check = await _db.workspaces.find_one({"workspace_id": _workspace_id}, {"_id": 0, "tpm_agent_id": 1})
                    if ws_check:
                        tpm_nxa = await _db.nexus_agents.find_one({"agent_id": ws_check.get("tpm_agent_id")}, {"_id": 0, "base_model": 1})
                        if tpm_nxa and tpm_nxa.get("base_model") == agent_key:
                            is_tpm_agent = True
                
                if is_tpm_agent:
                    import re
                    code_blocks_found = re.findall(r'```[\s\S]*?```', visible_text)
                    if code_blocks_found:
                        for block in code_blocks_found:
                            visible_text = visible_text.replace(block, "\n_[Code block removed — TPM agents must not write code. Assign coding tasks to the appropriate agent.]_\n")
                        logger.info(f"TPM {agent_key}: stripped {len(code_blocks_found)} code blocks from response")
                    
                    # TPM auto-posts directives to the TPM queue when giving instructions
                    try:
                        directive_keywords = ["you should", "your task", "please work on", "i need you to", "assigned to", "focus on", "priority:", "next step"]
                        content_lower = visible_text.lower()
                        if any(kw in content_lower for kw in directive_keywords):
                            await _db.tpm_queue.insert_one({
                                "directive_id": f"tpmd_{uuid.uuid4().hex[:12]}",
                                "workspace_id": _workspace_id,
                                "channel_id": _channel_id,
                                "tpm_agent": agent_key,
                                "directive": visible_text[:500],
                                "target_agent": "all",
                                "priority": "normal",
                                "status": "active",
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            })
                    except Exception as _e:
                        import logging; logging.getLogger("collaboration_core").warning(f"Suppressed: {_e}")

                ai_message = {
                    "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                    "channel_id": _channel_id,
                    "sender_type": "ai",
                    "sender_id": agent_key,
                    "sender_name": model_config["name"],
                    "ai_model": agent_key,
                    "content": visible_text,
                    "tool_calls": [{"tool": tc.get("tool"), "params": tc.get("params") or {}} for tc in tool_calls] if tool_calls else None,
                    "key_source": key_source,
                    "ai_generated": True,
                    "ai_provider": model_config.get("provider", ""),
                    "ai_model_id": model_config.get("model", ""),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                
                # HARD STOP CHECK: If persist was stopped mid-response, batch instead of posting
                if await state_get("collab:stop", _channel_id):
                    if _channel_id not in _pending_batch:
                        _pending_batch[_channel_id] = []
                    _pending_batch[_channel_id].append(ai_message)
                    logger.info(f"Hard stop: batched response from {agent_key} in {_channel_id}")
                    return
                
                await _db.messages.insert_one(ai_message)
                
                # Score confidence on the response
                try:
                    from confidence_scoring import estimate_confidence
                    confidence = estimate_confidence(visible_text)
                    await _db.messages.update_one(
                        {"message_id": ai_message["message_id"]},
                        {"$set": {"confidence": confidence}}
                    )
                except Exception as _e:
                    logger.debug(f"Silent exception: {_e}")
                
                # Save agent state to workspace memory
                await _save_agent_state(agent_key, f"Responded in {_channel_id}: {visible_text[:150]}")
                
                # Broadcast AI message via WebSocket
                try:
                    ai_message_clean = {k: v for k, v in ai_message.items() if k != "_id"}
                    await _ws_manager.broadcast(_channel_id, {"type": "new_message", "message": ai_message_clean})
                except Exception as _exc:
                    logger.debug(f"Non-critical error: {_exc}")
                
                # Log AI response as activity
                try:
                    await _db.workspace_activities.insert_one({
                        "activity_id": f"act_{uuid.uuid4().hex[:12]}",
                        "workspace_id": _workspace_id,
                        "channel_id": _channel_id,
                        "agent": model_config["name"],
                        "agent_key": agent_key,
                        "action_type": "ai_response",
                        "module": "collaboration",
                        "status": "success",
                        "summary": visible_text[:300],
                        "has_tool_calls": bool(tool_calls),
                        "has_violations": bool(violations) if 'violations' in dir() else False,
                        "response_time_ms": response_time_ms,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as _exc:
                    logger.debug(f"Non-critical error: {_exc}")

                # Execute tool calls and post results
                tool_results_text = ""
                for tc in tool_calls:
                    result = await execute_tool(_db, tc, _workspace_id, model_config["name"], _channel_id)
                    tool_results_text += f"\n[Tool Result: {tc.get('tool')}] {result['message'][:500]}\n"
                    tool_msg = {
                        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                        "channel_id": _channel_id,
                        "sender_type": "tool",
                        "sender_id": agent_key,
                        "sender_name": model_config["name"],
                        "ai_model": agent_key,
                        "content": result["message"],
                        "tool_result": result,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await _db.messages.insert_one(tool_msg)

                # Store analytics
                code_blocks = response_text.count("```") // 2
                try:
                    from routes_analytics import calculate_code_quality
                    code_quality = calculate_code_quality(response_text)
                except Exception as _e:
                    logger.warning(f"Code quality calc failed: {_e}")
                    code_quality = 0

                await _db.analytics.insert_one({
                    "analytics_id": f"an_{uuid.uuid4().hex[:12]}",
                    "channel_id": _channel_id,
                    "workspace_id": _workspace_id,
                    "agent": agent_key,
                    "response_time_ms": response_time_ms,
                    "content_length": len(response_text),
                    "code_blocks": code_blocks,
                    "code_quality_score": code_quality,
                    "key_source": key_source,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # --- REPORTING EVENT — feed the enterprise analytics pipeline ---
                try:
                    from routes_reporting import log_ai_event
                    # Get org_id from workspace
                    _ws = await _db.workspaces.find_one({"workspace_id": _workspace_id}, {"_id": 0, "org_id": 1, "owner_id": 1})
                    _org_id = _ws.get("org_id") if _ws else None
                    _owner_id = _ws.get("owner_id", user_id) if _ws else user_id
                    await log_ai_event(
                        _db, _owner_id, _org_id, _workspace_id, _channel_id,
                        model_config.get("provider", "unknown"), model_config.get("model", ""),
                        agent_key, key_source,
                        context_snapshot, response_text, response_time_ms,
                        status_code=200, thread_id=_channel_id,
                    )
                except Exception as _re:
                    logger.debug(f"Reporting event log failed: {_re}")

                # === MANAGED KEY CREDIT DEDUCTION ===
                if key_source == "nexus_managed":
                    try:
                        from managed_keys import deduct_credits
                        _tokens_in = len(context_snapshot) // 4  # Rough estimate
                        _tokens_out = len(response_text) // 4
                        await deduct_credits(user_id, effective_agent_key, _tokens_in, _tokens_out)
                    except Exception as _ce:
                        logger.debug(f"Credit deduction failed: {_ce}")

                # === NEXUS AI USAGE EVENT LOGGING / WARN THRESHOLDS ===
                try:
                    from managed_keys import record_usage_event, estimate_ai_cost_usd, check_usage_budget, emit_budget_alert
                    _org_for_usage = _ws.get("org_id") if _ws else None
                    _tokens_in_usage = len(context_snapshot) // 4
                    _tokens_out_usage = len(response_text) // 4
                    _cost_usage = estimate_ai_cost_usd(effective_agent_key, _tokens_in_usage, _tokens_out_usage)
                    pre_budget = await check_usage_budget(
                        effective_agent_key,
                        _cost_usage,
                        workspace_id=_workspace_id,
                        org_id=_org_for_usage,
                        user_id=user_id,
                    )
                    await record_usage_event(
                        effective_agent_key,
                        _cost_usage,
                        user_id=user_id,
                        workspace_id=_workspace_id,
                        org_id=_org_for_usage,
                        usage_type="ai",
                        key_source=key_source,
                        tokens_in=_tokens_in_usage,
                        tokens_out=_tokens_out_usage,
                        metadata={"channel_id": _channel_id, "agent_key": agent_key, "model": model_config.get("model", "")},
                    )
                    if pre_budget.get("warn"):
                        scope_name = (pre_budget.get("scope_type") or "platform").capitalize()
                        await emit_budget_alert(
                            effective_agent_key,
                            pre_budget.get("scope_type") or "platform",
                            pre_budget.get("scope_id") or "platform",
                            "warning",
                            pre_budget.get("projected_spend_usd", _cost_usage),
                            pre_budget.get("warn_threshold_usd"),
                            user_id=user_id,
                            workspace_id=_workspace_id,
                            org_id=_org_for_usage,
                            message=f"{scope_name} Nexus AI budget warning for {effective_agent_key}.",
                        )
                        await _db.messages.insert_one({
                            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                            "channel_id": _channel_id,
                            "sender_type": "system",
                            "sender_id": "system",
                            "sender_name": "System",
                            "content": f"_{scope_name} Nexus AI budget warning for {effective_agent_key}: ${pre_budget.get('projected_spend_usd', 0):.2f} has reached the warning threshold._",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception as _usage_err:
                    logger.debug(f"Usage event logging failed: {_usage_err}")
                try:
                    if is_nexus_agent and nexus_agent and (nexus_agent.get("training") or {}).get("enabled"):
                        _learn_threshold = 300  # Only learn from substantial responses
                        if len(visible_text) > _learn_threshold and tool_calls:
                            # Extract knowledge when agent uses tools (indicates active work)
                            from agent_training_crawler import chunk_content, tokenize_for_retrieval, classify_category
                            _learn_chunks = chunk_content(visible_text, "", max_chunk_size=500)
                            for _lc in _learn_chunks[:2]:  # Max 2 chunks per message
                                _tokens = tokenize_for_retrieval(_lc["content"])
                                await _db.agent_knowledge.insert_one({
                                    "chunk_id": f"kn_{uuid.uuid4().hex[:12]}",
                                    "agent_id": agent_key,
                                    "workspace_id": _workspace_id,
                                    "session_id": "conversation_learning",
                                    "content": _lc["content"],
                                    "summary": _lc["content"][:200],
                                    "category": classify_category(_lc["content"]),
                                    "topic": f"conversation:{_channel_id[:12]}",
                                    "tags": ["auto-learned", "conversation"],
                                    "source": {"type": "conversation", "channel_id": _channel_id, "message_id": ai_message["message_id"]},
                                    "tokens": _tokens,
                                    "token_count": _lc.get("token_count", len(_tokens)),
                                    "quality_score": 0.6,
                                    "source_authority": "medium",
                                    "flagged": False,
                                    "times_retrieved": 0,
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                })
                except Exception as _learn_err:
                    logger.debug(f"Conversation learning failed: {_learn_err}")

                # --- CONTEXT LEDGER — track context switches ---
                try:
                    from routes_context_ledger import save_context_entry
                    # Detect what triggered this response
                    last_msg_before = None
                    for msg in reversed(messages):
                        if msg.get("sender_id") != agent_key:
                            last_msg_before = msg
                            break
                    
                    if last_msg_before:
                        sender_type = last_msg_before.get("sender_type", "")
                        trigger_text = last_msg_before.get("content", "")[:300]
                        
                        # Determine event type
                        if sender_type == "human":
                            evt_type = "human_interrupt"
                            trigger_src = f"human:{last_msg_before.get('sender_name', '?')}"
                        elif sender_type == "ai":
                            # Check for disagreement
                            lower_resp = visible_text.lower()
                            disagree_signals = any(w in lower_resp for w in ["disagree", "incorrect", "actually", "however", "i would argue", "that's not", "wrong approach"])
                            evt_type = "disagreement" if disagree_signals else "context_switch"
                            trigger_src = f"agent:{last_msg_before.get('sender_name', '?')}"
                        else:
                            evt_type = "context_switch"
                            trigger_src = sender_type
                        
                        # Get prior work from agent's most recent message
                        prior_work = ""
                        for msg in reversed(messages):
                            if msg.get("sender_id") == agent_key and msg.get("sender_type") == "ai":
                                prior_work = msg.get("content", "")[:300]
                                break
                        
                        # Get linked project
                        proj_id = None
                        linked = channel.get("linked_projects") or []
                        if linked:
                            proj_id = linked[0] if isinstance(linked[0], str) else linked[0].get("project_id")
                        
                        await save_context_entry(
                            _db, _channel_id, _workspace_id, agent_key, model_config["name"],
                            evt_type, prior_work, trigger_text, trigger_src,
                            response_summary=visible_text[:300], project_id=proj_id
                        )
                except Exception as ctx_save_err:
                    logger.warning(f"Context ledger save failed: {ctx_save_err}")

                # --- AUTO-ARTIFACT FROM CODE BLOCKS ---
                # If AI generated significant code, auto-save as artifact
                if code_blocks >= 1:
                    try:
                        import re as _re
                        code_matches = _re.findall(r'```(\w*)\n(.*?)```', visible_text, _re.DOTALL)
                        for lang, code_content in code_matches[:3]:  # Max 3 artifacts per message
                            if lang == "mermaid" and len(code_content.strip()) > 20:
                                # Save mermaid diagrams as diagram artifacts
                                art_id = f"art_{uuid.uuid4().hex[:12]}"
                                art_name = f"{model_config['name']} — diagram"
                                await _db.artifacts.insert_one({
                                    "artifact_id": art_id, "workspace_id": _workspace_id,
                                    "name": art_name, "content": code_content.strip(),
                                    "content_type": "diagram", "tags": ["auto-generated", "from-chat", "mermaid", agent_key],
                                    "pinned": False, "version": 1, "attachments": [],
                                    "created_by": f"ai:{model_config['name']}",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                })
                            elif len(code_content.strip()) > 50:  # Only for substantial code
                                art_id = f"art_{uuid.uuid4().hex[:12]}"
                                art_name = f"{model_config['name']} — {lang or 'code'} snippet"
                                await _db.artifacts.insert_one({
                                    "artifact_id": art_id, "workspace_id": _workspace_id,
                                    "name": art_name, "content": code_content.strip(),
                                    "content_type": "code", "tags": ["auto-generated", "from-chat", lang or "code", agent_key],
                                    "pinned": False, "version": 1, "attachments": [],
                                    "created_by": f"ai:{model_config['name']}",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                })
                                await _db.artifact_versions.insert_one({
                                    "artifact_id": art_id, "version": 1,
                                    "content": code_content.strip(),
                                    "created_by": f"ai:{model_config['name']}",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                })
                    except Exception as art_err:
                        logger.warning(f"Auto-artifact creation failed: {art_err}")

                # --- AUTO-ARTIFACT FROM INLINE IMAGES ---
                try:
                    import re as _re_img
                    image_urls = _re_img.findall(r'!\[([^\]]*)\]\((https?://[^)]+\.(?:png|jpg|jpeg|gif|webp|svg)[^)]*)\)', visible_text)
                    standalone_urls = _re_img.findall(r'(?:^|\n)(https?://\S+\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?\S*)?)', visible_text)
                    all_images = [(alt, url) for alt, url in image_urls] + [("Generated image", url) for url in standalone_urls]
                    for alt, img_url in all_images[:3]:
                        art_id = f"art_{uuid.uuid4().hex[:12]}"
                        art_name = f"{model_config['name']} — {alt or 'image'}"
                        await _db.artifacts.insert_one({
                            "artifact_id": art_id, "workspace_id": _workspace_id,
                            "name": art_name, "content": img_url,
                            "content_type": "image", "tags": ["auto-generated", "from-chat", "image", agent_key],
                            "pinned": False, "version": 1,
                            "attachments": [{"type": "image", "url": img_url, "name": alt or "image"}],
                            "created_by": f"ai:{model_config['name']}",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception as img_art_err:
                    logger.warning(f"Auto-artifact from image failed: {img_art_err}")

                # --- SAVE TO REPO DETECTION ---
                # Check if agent wants to save code to the repository
                try:
                    import re as _re2
                    save_matches = _re2.findall(
                        r':::SAVE_TO_REPO\s+([\w./\-]+):::\s*```\w*\n(.*?)```\s*:::END_SAVE:::', 
                        response_text, _re2.DOTALL
                    )
                    if save_matches:
                        for file_path, code_content in save_matches[:3]:
                            code_content = code_content.strip()
                            if len(code_content) < 10:
                                continue
                            # Queue for QA - pick a different agent to review
                            qa_agents = [a for a in target_agents if a != agent_key and a in AI_MODELS]
                            if qa_agents:
                                qa_agent_key = qa_agents[0]
                                qa_model = AI_MODELS[qa_agent_key]
                                qa_api_key, _ = await get_ai_key_for_agent(user_id, _workspace_id, qa_agent_key)
                                
                                if qa_api_key:
                                    # Ask QA agent to review
                                    qa_prompt = f"""Review this code before it's committed to the repository.
File: {file_path}
Author: {model_config['name']}

```
{code_content}
```

Respond with either:
- "QA APPROVED" if the code is ready to commit (brief reason)
- "QA REJECTED" if there are issues (explain what needs fixing)

Be concise (under 100 words)."""
                                    
                                    try:
                                        qa_response = await call_ai_direct(
                                            qa_agent_key, qa_api_key,
                                            f"You are {qa_model['name']}, a code reviewer. Review code for correctness, security, and quality.",
                                            qa_prompt,
                                            workspace_id=_workspace_id, db=_db, channel_id=_channel_id
                                        )
                                        
                                        qa_approved = "QA APPROVED" in qa_response.upper() or "APPROVED" in qa_response.upper()[:50]
                                        
                                        # Post QA review message
                                        qa_msg = {
                                            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                                            "channel_id": _channel_id,
                                            "sender_type": "ai",
                                            "sender_id": qa_agent_key,
                                            "sender_name": qa_model["name"],
                                            "ai_model": qa_agent_key,
                                            "content": f"**Code Review for `{file_path}`:**\n{qa_response}",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await _db.messages.insert_one(qa_msg)
                                        
                                        if qa_approved:
                                            # Commit to repo
                                            existing = await _db.repo_files.find_one(
                                                {"workspace_id": _workspace_id, "path": file_path, "is_deleted": {"$ne": True}}
                                            )
                                            now_ts = datetime.now(timezone.utc).isoformat()
                                            
                                            if existing:
                                                old_content = existing.get("content", "")
                                                new_ver = existing.get("version", 0) + 1
                                                await _db.repo_files.update_one(
                                                    {"file_id": existing["file_id"]},
                                                    {"$set": {"content": code_content, "size": len(code_content.encode("utf-8")),
                                                              "version": new_ver, "updated_by": f"ai:{model_config['name']}",
                                                              "updated_at": now_ts}}
                                                )
                                                file_id = existing["file_id"]
                                            else:
                                                file_id = f"rf_{uuid.uuid4().hex[:12]}"
                                                fname = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
                                                ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
                                                lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "html": "html", "css": "css", "json": "json"}
                                                new_ver = 1
                                                old_content = ""
                                                await _db.repo_files.insert_one({
                                                    "file_id": file_id, "workspace_id": _workspace_id,
                                                    "path": file_path, "name": fname, "is_folder": False,
                                                    "language": lang_map.get(ext, "plaintext"),
                                                    "content": code_content, "size": len(code_content.encode("utf-8")),
                                                    "version": 1, "created_by": f"ai:{model_config['name']}",
                                                    "updated_by": f"ai:{model_config['name']}",
                                                    "created_at": now_ts, "updated_at": now_ts, "is_deleted": False,
                                                })
                                                # Ensure repo exists
                                                repo = await _db.code_repos.find_one({"workspace_id": _workspace_id})
                                                if not repo:
                                                    await _db.code_repos.insert_one({
                                                        "repo_id": f"repo_{uuid.uuid4().hex[:12]}",
                                                        "workspace_id": _workspace_id,
                                                        "created_at": now_ts, "updated_at": now_ts, "file_count": 0,
                                                    })
                                            
                                            # Create commit
                                            await _db.repo_commits.insert_one({
                                                "commit_id": f"rc_{uuid.uuid4().hex[:12]}",
                                                "workspace_id": _workspace_id, "file_id": file_id,
                                                "file_path": file_path, "action": "update" if existing else "create",
                                                "message": f"{model_config['name']}: saving to repo (QA by {qa_model['name']})",
                                                "author_id": f"ai:{model_config['name']}",
                                                "author_name": model_config["name"],
                                                "content_before": old_content[:50000],
                                                "content_after": code_content[:50000],
                                                "version": new_ver,
                                                "created_at": now_ts,
                                            })
                                            
                                            # Post saving to repo confirmation
                                            save_msg = {
                                                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                                                "channel_id": _channel_id,
                                                "sender_type": "system",
                                                "sender_id": "system",
                                                "sender_name": "System",
                                                "content": f"**saving to repo** — `{file_path}` committed by {model_config['name']} (QA approved by {qa_model['name']})",
                                                "created_at": datetime.now(timezone.utc).isoformat()
                                            }
                                            await _db.messages.insert_one(save_msg)
                                            logger.info(f"Code saved to repo: {file_path} by {model_config['name']}")
                                    except Exception as qa_err:
                                        logger.warning(f"QA review failed: {qa_err}")
                except Exception as repo_err:
                    logger.warning(f"Save-to-repo detection failed: {repo_err}")

                # --- AUTO HANDOFF EXTRACTION ---
                # Generate structured handoff summary after each AI response
                try:
                    handoff_data = {
                        "source_agent": model_config["name"],
                        "task_summary": visible_text[:300],
                        "confidence": 0.8,
                        "open_questions": [],
                        "assumptions": [],
                        "channel_id": _channel_id,
                        "workspace_id": _workspace_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    # Simple heuristic extraction
                    lower = visible_text.lower()
                    if "?" in visible_text:
                        questions = [s.strip() + "?" for s in visible_text.split("?") if len(s.strip()) > 10][:3]
                        handoff_data["open_questions"] = questions
                    if any(w in lower for w in ["assume", "assuming", "presumably", "likely"]):
                        handoff_data["assumptions"].append("Contains assumptions — verify before proceeding")
                    if any(w in lower for w in ["not sure", "uncertain", "might", "possibly"]):
                        handoff_data["confidence"] = 0.6
                    elif any(w in lower for w in ["definitely", "certainly", "confirmed", "verified"]):
                        handoff_data["confidence"] = 0.95
                    await _db.handoff_extractions.insert_one(handoff_data)
                    # Attach to message
                    await _db.messages.update_one(
                        {"message_id": ai_message["message_id"]},
                        {"$set": {"handoff_summary": {
                            "confidence": handoff_data["confidence"],
                            "open_questions": handoff_data["open_questions"],
                            "assumptions": handoff_data["assumptions"],
                        }}}
                    )
                except Exception as he:
                    logger.warning(f"Handoff extraction failed: {he}")

            except Exception as e:
                error_str = str(e)
                # Rate-limited agents skip silently — no error message spam
                if error_str.startswith("RATE_LIMITED:"):
                    provider = error_str.split(":", 1)[1] if ":" in error_str else agent_key
                    logger.info(f"Agent {agent_key} ({provider}) rate limited — skipping this round")
                    # Log to activity for the error log feature
                    try:
                        await _db.workspace_activities.insert_one({
                            "activity_id": f"act_{uuid.uuid4().hex[:12]}",
                            "workspace_id": _workspace_id,
                            "channel_id": _channel_id,
                            "agent": model_config["name"],
                            "agent_key": agent_key,
                            "action_type": "rate_limited",
                            "module": "collaboration",
                            "status": "skipped",
                            "summary": f"Rate limited by {provider} — skipped this round",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception as _e:
                        logger.debug(f"Silent exception: {_e}")
                    return
                
                logger.error(f"Error with {agent_key}: {e}")
                lowered_error = error_str.lower()
                content = f"_I encountered an issue: {error_str}_"
                if "universal key budget is exhausted" in lowered_error or "budget has been exceeded" in lowered_error or "max budget" in lowered_error:
                    content = f"_{model_config['name']} paused: the platform Nexus AI budget is exhausted. Ask an admin to review Settings → Nexus AI budgets, or save your own provider key in Settings → AI Keys._"
                elif "no api key provided" in lowered_error or "configure in settings" in lowered_error:
                    content = f"_{model_config['name']} could not start because the configured platform AI key is invalid and no fallback capacity is available. Update Platform Keys, or save your own provider key in Settings → AI Keys._"
                error_msg = {
                    "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                    "channel_id": _channel_id,
                    "sender_type": "ai",
                    "sender_id": agent_key,
                    "sender_name": model_config["name"],
                    "ai_model": agent_key,
                    "content": content,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await _db.messages.insert_one(error_msg)
                # Log error as activity
                try:
                    await _db.workspace_activities.insert_one({
                        "activity_id": f"act_{uuid.uuid4().hex[:12]}",
                        "workspace_id": _workspace_id,
                        "channel_id": _channel_id,
                        "agent": model_config["name"],
                        "agent_key": agent_key,
                        "action_type": "error",
                        "module": "collaboration",
                        "status": "error",
                        "summary": str(e)[:300],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as _exc:
                    logger.debug(f"Non-critical error: {_exc}")
            finally:
                await state_delete("collab:active", f"{_channel_id}_{agent_key}")
        
        # --- DISPATCH AGENTS (TPM-first if assigned) ---
        if target_agents:
            import random
            
            # Get channel roles
            channel_roles = channel.get("channel_roles") or {}
            tpm_agent = channel_roles.get("tpm")
            _architect_agent = channel_roles.get("architect")  # Used by agent prompts
            
            async def staggered_agent(ak, ctx, delay, ws_id, ch_id):
                if delay > 0:
                    await asyncio.sleep(delay)
                return await run_single_agent(ak, ctx, ws_id=ws_id, ch_id=ch_id)
            
            if tpm_agent and tpm_agent in target_agents:
                # TPM speaks FIRST — alone, before other agents
                logger.info(f"TPM agent {tpm_agent} speaking first in {channel_id}")
                await run_single_agent(tpm_agent, context, ws_id=workspace_id, ch_id=channel_id)
                
                # Refresh context to include TPM's response
                updated_msgs = await _db.messages.find(
                    {"channel_id": channel_id}, {"_id": 0}
                ).sort("created_at", -1).to_list(50)
                updated_msgs.reverse()
                context_with_tpm = "Here is the conversation so far:\n\n"
                for msg in updated_msgs:
                    sender = msg.get("sender_name", "Unknown")
                    context_with_tpm += f"[{sender}]: {msg['content']}\n\n"
                
                # Other agents respond with TPM's direction in context
                other_agents = [a for a in target_agents if a != tpm_agent]
                if other_agents:
                    agent_tasks = []
                    for i, ak in enumerate(other_agents):
                        delay = i * 2.5 + random.uniform(0.5, 1.5)
                        agent_tasks.append(staggered_agent(ak, context_with_tpm, delay, workspace_id, channel_id))
                    await asyncio.gather(*agent_tasks, return_exceptions=True)
            else:
                # No TPM — all agents in parallel (original behavior)
                agent_tasks = []
                for i, ak in enumerate(target_agents):
                    delay = i * 2.5 + random.uniform(0.5, 1.5)
                    agent_tasks.append(staggered_agent(ak, context, delay, workspace_id, channel_id))
                await asyncio.gather(*agent_tasks, return_exceptions=True)
        
        # Send notification after all agents have responded
        try:
            from routes_notifications import notify_channel_response
            # Get workspace members and owner in one query
            workspace = await _db.workspaces.find_one(
                {"workspace_id": workspace_id},
                {"_id": 0, "owner_id": 1, "members": 1}
            )
            member_ids = list(workspace.get("members") or []) if workspace else []
            if workspace and workspace.get("owner_id"):
                owner_id = workspace["owner_id"]
                if owner_id not in member_ids:
                    member_ids.append(owner_id)
            
            # Don't notify the user who triggered the collaboration
            member_ids = [uid for uid in member_ids if uid != user_id]
            
            if member_ids:
                await notify_channel_response(_db, channel_id, "AI Agents", member_ids)
        except Exception as notif_err:
            logger.warning(f"Failed to send channel notification: {notif_err}")

        # --- AUTO DISAGREEMENT DETECTION ---
        # Check if multiple agents responded with conflicting information
        try:
            recent_ai = await _db.messages.find(
                {"channel_id": channel_id, "sender_type": "ai"},
                {"_id": 0, "content": 1, "sender_name": 1, "ai_model": 1}
            ).sort("created_at", -1).limit(len(target_agents)).to_list(len(target_agents))
            
            if len(recent_ai) >= 2:
                # Simple conflict detection: check for contradictory language
                contents = [m.get("content", "").lower() for m in recent_ai]
                conflict_signals = 0
                for i, c in enumerate(contents):
                    for j, c2 in enumerate(contents):
                        if i >= j:
                            continue
                        # Check for disagreement patterns
                        if any(phrase in c for phrase in ["disagree", "incorrect", "wrong", "not accurate", "i don't think"]):
                            conflict_signals += 2
                        if any(phrase in c for phrase in ["however", "on the other hand", "alternatively", "but i would"]):
                            conflict_signals += 1
                
                if conflict_signals >= 3:
                    dis_id = f"dis_{uuid.uuid4().hex[:12]}"
                    agents_involved = [{"model": m["ai_model"], "position_summary": m["content"][:200]} for m in recent_ai]
                    await _db.disagreements.insert_one({
                        "disagreement_id": dis_id,
                        "channel_id": channel_id,
                        "workspace_id": workspace_id,
                        "topic": "Auto-detected from recent AI responses",
                        "status": "detected",
                        "agents_involved": agents_involved,
                        "votes": {},
                        "resolution": None,
                        "auto_detected": True,
                        "conflict_score": conflict_signals,
                        "created_by": "system",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    # Post notification in channel
                    await _db.messages.insert_one({
                        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                        "channel_id": channel_id,
                        "sender_type": "system",
                        "sender_id": "system",
                        "sender_name": "System",
                        "content": f"_Disagreement detected between agents. [View Resolution](/disagreements/{dis_id})_",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(f"Auto-detected disagreement {dis_id} with score {conflict_signals}")
        except Exception as dis_err:
            logger.warning(f"Disagreement detection failed: {dis_err}")

    except Exception as e:
        logger.error(f"Collaboration error: {e}")
    finally:
        # Don't pop the running flag if called from persist loop (persist manages its own flag)
        if not called_from_persist:
            await state_delete("collab:active", f"{channel_id}_running")

# Task session agent runner
active_task_sessions = {}

async def run_persist_collaboration(channel_id: str, user_id: str):
    """Persistent collaboration loop — runs until manually stopped, with adaptive throttling and agent health management"""
    try:
        session = await state_get("collab:persist", channel_id)
        if not session:
            return

        logger.info(f"Persist collab started for {channel_id}")
        session["status"] = "running"
        session["agent_errors"] = {}  # {agent_key: consecutive_error_count}
        session["auto_disabled_agents"] = []

        while True:
            # Check if still enabled OR hard stopped
            session = await state_get("collab:persist", channel_id)
            if not session or not session.get("enabled") or await state_get("collab:stop", channel_id):
                _hs = await state_get("collab:stop", channel_id)
                logger.info(f"Persist collab stopped for {channel_id} (hard_stop={_hs})")
                break

            session["round"] = session.get("round", 0) + 1
            current_round = session["round"]
            current_delay = session.get("delay", 3)

            logger.info(f"Persist round {current_round} for {channel_id} (delay: {current_delay}s)")
            session["status"] = f"round {current_round}"

            # Human Priority Check — pause if human sent a message
            hp = await state_get("collab:priority", channel_id)
            if hp and hp.get("pause_requested") and not hp.get("processed"):
                session["status"] = "paused (human priority)"
                logger.info(f"Persist pausing for human priority in {channel_id}")
                # Wait for human message to be processed (up to 30 seconds)
                for _ in range(30):
                    hp = await state_get("collab:priority", channel_id)
                    if not hp or hp.get("processed"):
                        break
                    await asyncio.sleep(1)
                # Clear the priority flag
                human_priority.pop(channel_id, None)
                session["status"] = "resuming after human input"
                # Skip this round — the human priority round already ran
                continue

            try:
                # Run one collaboration round
                round_start = datetime.now(timezone.utc).isoformat()
                await run_ai_collaboration(channel_id, user_id, called_from_persist=True)
                
                # Check if agents actually produced any AI responses this round
                ai_responses = await _db.messages.count_documents({
                    "channel_id": channel_id,
                    "sender_type": "ai",
                    "created_at": {"$gte": round_start},
                    "content": {"$not": {"$regex": "encountered an issue"}}
                })
                
                if ai_responses > 0:
                    # Success — reduce delay (speed up), reset error count
                    session["consecutive_errors"] = 0
                    new_delay = max(session.get("min_delay", 3), current_delay * 0.9)
                    session["delay"] = round(new_delay, 1)
                    session["status"] = f"round {current_round} complete"
                else:
                    # No useful AI responses — agents are erroring or skipping
                    session["consecutive_errors"] = session.get("consecutive_errors", 0) + 1
                    errors = session["consecutive_errors"]
                    new_delay = min(session.get("max_delay", 120), current_delay * 1.3)
                    session["delay"] = round(new_delay, 1)
                    session["status"] = f"round {current_round} — no agent responses ({errors} consecutive)"
                    logger.warning(f"Persist round {current_round}: no AI responses in {channel_id} (err count: {errors})")
                    
                    # Stop persist if too many rounds with no responses
                    if errors >= 10:
                        logger.error(f"Persist stopping: {errors} rounds with no AI responses in {channel_id}")
                        await _db.messages.insert_one({
                            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                            "channel_id": channel_id,
                            "sender_type": "system",
                            "sender_id": "system",
                            "sender_name": "System",
                            "content": f"_Persistent collaboration stopped: No agent responses for {errors} consecutive rounds. Check your API keys in Settings._",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        })
                        break

            except Exception as e:
                error_msg = str(e)[:200]
                session["consecutive_errors"] = session.get("consecutive_errors", 0) + 1
                errors = session["consecutive_errors"]
                logger.warning(f"Persist round {current_round} error ({errors}): {error_msg}")

                if "rate limit" in error_msg.lower() or "429" in error_msg:
                    new_delay = min(session.get("max_delay", 120), current_delay * 2.5)
                    session["delay"] = round(new_delay, 1)
                    session["status"] = f"throttled (rate limit) — {new_delay:.0f}s delay"
                else:
                    new_delay = min(session.get("max_delay", 120), current_delay * 1.5)
                    session["delay"] = round(new_delay, 1)
                    session["status"] = f"error recovery — {new_delay:.0f}s delay"

            # --- Per-agent health check (every 5 rounds) ---
            if current_round % 5 == 0:
                try:
                    channel = await _db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
                    if channel:
                        all_agents = channel.get("ai_agents") or []
                        disabled = channel.get("disabled_agents") or []
                        auto_disabled = session.get("auto_disabled_agents") or []
                        
                        # Check recent messages for agent errors (exclude "requires API key" — that's expected, not an error)
                        recent_msgs = await _db.messages.find(
                            {"channel_id": channel_id, "sender_type": {"$in": ["system", "ai"]},
                             "content": {"$regex": "encountered an issue|API error|fatal|timed out",
                                         "$not": {"$regex": "requires an API key"}}},
                            {"_id": 0, "content": 1, "created_at": 1}
                        ).sort("created_at", -1).limit(20).to_list(20)
                        
                        # Count errors per agent
                        for agent_key in all_agents:
                            agent_errors = sum(1 for m in recent_msgs if agent_key in m.get("content", "").lower() or 
                                             (AI_MODELS.get(agent_key, {}).get("name", "").lower() in m.get("content", "").lower()))
                            if agent_errors >= 3 and agent_key not in disabled and agent_key not in auto_disabled:
                                # Auto-disable this agent
                                await _db.channels.update_one(
                                    {"channel_id": channel_id},
                                    {"$addToSet": {"disabled_agents": agent_key}}
                                )
                                auto_disabled.append(agent_key)
                                session["auto_disabled_agents"] = auto_disabled
                                logger.warning(f"Persist auto-disabled {agent_key} in {channel_id} (3+ errors)")
                                
                                await _db.messages.insert_one({
                                    "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                                    "channel_id": channel_id,
                                    "sender_type": "system",
                                    "sender_id": "system",
                                    "sender_name": "System",
                                    "content": f"_Auto-disabled **{AI_MODELS.get(agent_key, {}).get('name', agent_key)}** due to repeated errors. Other agents continue working._",
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                })
                        
                        # Check if 50%+ of ACTIVE agents failed — stop persist entirely
                        # Only count agents that were active (not user-disabled) as the baseline
                        active_agents = [a for a in all_agents if a not in disabled or a in auto_disabled]
                        total_active = len(active_agents)
                        # Only auto-disabled agents count as failures (user-disabled are intentional)
                        failed_count = len(auto_disabled)
                        if total_active > 0 and failed_count >= (total_active / 2):
                            logger.error(f"Persist stopping: {failed_count}/{total_active} active agents failed in {channel_id}")
                            
                            # Notify workspace admin
                            ws_id = channel.get("workspace_id", "")
                            now = datetime.now(timezone.utc).isoformat()
                            
                            # Find workspace owner/admins
                            ws = await _db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "owner_id": 1})
                            admin_ids = set()
                            if ws:
                                admin_ids.add(ws.get("owner_id", ""))
                            # Find workspace admins (role-based)
                            ws_admins = await _db.workspace_members.find(
                                {"workspace_id": ws_id, "role": {"$in": ["admin", "workspace_admin", "owner"]}},
                                {"_id": 0, "user_id": 1}
                            ).to_list(20)
                            for m in ws_admins:
                                admin_ids.add(m["user_id"])
                            # Find org admins if workspace belongs to an org
                            org_admins = await _db.org_memberships.find(
                                {"role": {"$in": ["admin", "owner"]}},
                                {"_id": 0, "user_id": 1}
                            ).to_list(20)
                            for m in org_admins:
                                admin_ids.add(m["user_id"])
                            admin_ids.discard("")
                            
                            # Send notification to all admins
                            failed_names = [AI_MODELS.get(a, {}).get("name", a) for a in auto_disabled]
                            for admin_id in admin_ids:
                                await _db.notifications.insert_one({
                                    "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                                    "user_id": admin_id,
                                    "type": "persist_stopped",
                                    "title": "Persistent Collaboration Stopped",
                                    "message": f"{failed_count}/{total_active} active agents failed in #{channel.get('name', channel_id)}: {', '.join(failed_names)}. Persist mode has been stopped.",
                                    "data": {"channel_id": channel_id, "workspace_id": ws_id},
                                    "read": False,
                                    "created_at": now,
                                })
                            
                            await _db.messages.insert_one({
                                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                                "channel_id": channel_id,
                                "sender_type": "system",
                                "sender_id": "system",
                                "sender_name": "System",
                                "content": f"_Persistent collaboration **stopped**: {failed_count}/{total_active} active agents have critical errors ({', '.join(failed_names)}). Workspace admins have been notified._",
                                "created_at": now,
                            })
                            break
                except Exception as health_err:
                    logger.warning(f"Agent health check failed: {health_err}")

            # Adaptive sleep with jitter (break early if hard stopped)
            sleep_time = session.get("delay", 3) + random.uniform(0, 2)
            for _ in range(int(sleep_time * 2)):
                if await state_get("collab:stop", channel_id):
                    break
                await asyncio.sleep(0.5)
            
            if await state_get("collab:stop", channel_id):
                logger.info(f"Persist hard stopped during sleep for {channel_id}")
                break

            # Periodic check — re-read from DB in case it was disabled
            if current_round % 10 == 0:
                ch = await _db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "auto_collab_persist": 1})
                if not ch or not ch.get("auto_collab_persist"):
                    logger.info(f"Persist disabled in DB for {channel_id}")
                    break

        # Post completion message
        final_round = (await state_get("collab:persist", channel_id) or {}).get("round", 0)
        await _db.messages.insert_one({
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "system",
            "sender_id": "system",
            "sender_name": "System",
            "content": f"_Persistent collaboration stopped after {final_round} rounds._",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Persist loop fatal error: {e}")
    finally:
        await state_delete("collab:persist", channel_id)
        await state_delete("collab:active", f"{channel_id}_running")
        await _db.channels.update_one(
            {"channel_id": channel_id},
            {"$set": {"auto_collab_persist": False}}
        )

# --- Agent Toggle (Disable/Enable per channel) ---

