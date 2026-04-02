from nexus_utils import now_iso
"""Agent Playground — Sandbox chat to test agents before deploying to channels.

Provides a simple request/response loop using the agent's assembled prompt.
Messages are stored in agent_playground_messages for history but don't affect
the real collaboration engine or channel state.
"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("agent_playground")



class PlaygroundMessage(BaseModel):
    content: str
    session_id: Optional[str] = None


def register_playground_routes(api_router, db, get_current_user):

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/playground")
    async def playground_chat(ws_id: str, agent_id: str, data: PlaygroundMessage, request: Request):
        """Send a message to an agent in sandbox mode and get a response."""
        user = await get_current_user(request)

        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": ws_id}, {"_id": 0}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")

        session_id = data.session_id or f"pg_{uuid.uuid4().hex[:12]}"

        # Build the agent's full system prompt (with skills, personality, RAG)
        from agent_prompt_builder import build_agent_prompt
        try:
            system_prompt = await build_agent_prompt(db, agent, ws_id, f"playground_{session_id}")
        except Exception:
            system_prompt = agent.get("system_prompt", "You are a helpful AI assistant.")

        # Get conversation history for this session
        history = await db.agent_playground_messages.find(
            {"session_id": session_id},
            {"_id": 0, "role": 1, "content": 1}
        ).sort("created_at", 1).limit(20).to_list(20)

        # Build messages for the AI call
        messages_for_ai = ""
        for msg in history:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            messages_for_ai += f"{prefix}: {msg['content']}\n"
        messages_for_ai += f"User: {data.content}\nAssistant:"

        # Get AI key
        from collaboration_core import get_ai_key_for_agent
        base_model = agent.get("base_model", "claude")
        api_key, key_source = await get_ai_key_for_agent(user["user_id"], ws_id, base_model)

        response_text = ""
        if api_key:
            try:
                from ai_providers import call_ai_direct
                response_text = await call_ai_direct(
                    base_model, api_key, system_prompt, messages_for_ai,
                    workspace_id=ws_id, db=db
                )
            except Exception as e:
                response_text = f"[Playground Error] AI call failed: {str(e)[:200]}"
        else:
            response_text = (
                f"[Playground] No API key available for {base_model}. "
                f"This agent has {len(agent.get('skills', []))} skills configured. "
                f"System prompt preview ({len(system_prompt)} chars):\n\n{system_prompt[:500]}..."
            )

        # Store messages
        now = now_iso()
        await db.agent_playground_messages.insert_one({
            "session_id": session_id, "agent_id": agent_id, "workspace_id": ws_id,
            "role": "user", "content": data.content, "created_at": now,
        })
        await db.agent_playground_messages.insert_one({
            "session_id": session_id, "agent_id": agent_id, "workspace_id": ws_id,
            "role": "assistant", "content": response_text,
            "model": base_model, "created_at": now_iso(),
        })

        return {
            "session_id": session_id,
            "response": response_text,
            "model": base_model,
            "prompt_length": len(system_prompt),
            "skills_count": len(agent.get("skills") or []),
            "has_knowledge": await db.agent_knowledge.count_documents({"agent_id": agent_id}) > 0,
        }

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/playground/{session_id}")
    async def get_playground_history(ws_id: str, agent_id: str, session_id: str, request: Request):
        """Get playground conversation history."""
        user = await get_current_user(request)
        messages = await db.agent_playground_messages.find(
            {"session_id": session_id, "agent_id": agent_id},
            {"_id": 0}
        ).sort("created_at", 1).limit(50).to_list(50)
        return {"session_id": session_id, "messages": messages}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/playground-sessions")
    async def list_playground_sessions(ws_id: str, agent_id: str, request: Request):
        """List all playground sessions for an agent."""
        user = await get_current_user(request)
        pipeline = [
            {"$match": {"agent_id": agent_id, "workspace_id": ws_id}},
            {"$group": {
                "_id": "$session_id",
                "message_count": {"$sum": 1},
                "last_message": {"$max": "$created_at"},
                "first_message": {"$min": "$created_at"},
            }},
            {"$sort": {"last_message": -1}},
            {"$limit": 20},
        ]
        sessions = []
        async for doc in db.agent_playground_messages.aggregate(pipeline):
            sessions.append({
                "session_id": doc["_id"],
                "message_count": doc["message_count"],
                "last_message": doc["last_message"],
                "started_at": doc["first_message"],
            })
        return {"sessions": sessions}

    @api_router.delete("/workspaces/{ws_id}/agents/{agent_id}/playground/{session_id}")
    async def delete_playground_session(ws_id: str, agent_id: str, session_id: str, request: Request):
        """Delete a playground session."""
        user = await get_current_user(request)
        result = await db.agent_playground_messages.delete_many(
            {"session_id": session_id, "agent_id": agent_id, "workspace_id": ws_id}
        )
        return {"deleted": result.deleted_count}

    @api_router.post("/workspaces/{ws_id}/playground/multi-agent")
    async def multi_agent_playground(ws_id: str, request: Request):
        """Agent-to-agent sandbox — two agents discuss a topic."""
        user = await get_current_user(request)
        body = await request.json()
        agent_ids = body.get("agent_ids") or [][:3]
        topic = body.get("topic", "")
        rounds = min(body.get("rounds", 3), 5)

        if len(agent_ids) < 2 or not topic:
            raise HTTPException(400, "Provide at least 2 agent_ids and a topic")

        # Load agents
        agents_data = []
        for aid in agent_ids:
            agent = await db.nexus_agents.find_one({"agent_id": aid, "workspace_id": ws_id}, {"_id": 0})
            if agent:
                agents_data.append(agent)
        if len(agents_data) < 2:
            raise HTTPException(400, "Could not find enough agents")

        session_id = f"multi_{uuid.uuid4().hex[:12]}"
        conversation = []

        # Build initial prompt
        agent_names = [a["name"] for a in agents_data]
        initial_prompt = f"Discussion topic: {topic}\nParticipants: {', '.join(agent_names)}\nEach participant should share their perspective, build on others' ideas, and work toward actionable conclusions."

        conversation.append({"role": "system", "agent": "moderator", "content": initial_prompt})

        # Run rounds — each agent responds in turn
        for rnd in range(rounds):
            for agent in agents_data:
                name = agent["name"]
                system_prompt = agent.get("system_prompt", "You are a helpful AI assistant.")

                # Build context from conversation so far
                context_msgs = [{"role": "system", "content": f"{system_prompt}\n\nYou are {name} in a group discussion. {initial_prompt}"}]
                for msg in conversation:
                    if msg["role"] != "system":
                        role = "assistant" if msg.get("agent") == name else "user"
                        context_msgs.append({"role": role, "content": f"[{msg['agent']}]: {msg['content']}"})
                if not conversation or conversation[-1].get("role") == "system":
                    context_msgs.append({"role": "user", "content": f"Start the discussion. You are {name}."})

                # Call AI
                try:
                    from ai_providers import call_ai_direct
                    base_model = agent.get("base_model", "chatgpt")
                    api_key = await _get_api_key(db, base_model)
                    model_name = _resolve_model(base_model)
                    system_msg = context_msgs[0]["content"] if context_msgs and context_msgs[0]["role"] == "system" else ""
                    user_msgs = [m for m in context_msgs if m["role"] != "system"]
                    user_text = "\n".join([m["content"] for m in user_msgs[-3:]])
                    reply = await call_ai_direct(base_model, api_key, system_msg, user_text)
                except Exception as e:
                    reply = f"[{name} could not respond: {str(e)[:100]}]"

                conversation.append({"role": "assistant", "agent": name, "content": reply, "round": rnd + 1})

        # Store session
        await db.agent_playground_sessions.insert_one({
            "session_id": session_id, "workspace_id": ws_id, "type": "multi_agent",
            "agent_ids": agent_ids, "topic": topic, "rounds": rounds,
            "conversation": conversation, "user_id": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"session_id": session_id, "conversation": conversation, "rounds": rounds}


async def _get_api_key(db, provider="chatgpt"):
    """Get API key for playground calls — resolves per provider."""
    from key_resolver import get_integration_key
    provider_key_map = {
        "chatgpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_AI_KEY", "deepseek": "DEEPSEEK_API_KEY",
        "mistral": "MISTRAL_API_KEY", "cohere": "COHERE_API_KEY",
        "grok": "GROK_API_KEY", "perplexity": "PERPLEXITY_API_KEY",
    }
    env_key = provider_key_map.get(provider, "OPENAI_API_KEY")
    try:
        key = await get_integration_key(db, env_key)
        if key:
            return key
    except Exception as e:
        logger.warning(f"Key resolution failed for {env_key}: {e}")
    import os
    return os.environ.get(env_key, "")


def _resolve_model(base_model):
    """Resolve base model name to API model identifier."""
    MODEL_MAP = {
        "chatgpt": "gpt-4o-mini", "gpt4": "gpt-4o", "claude": "claude-sonnet-4-20250514",
        "gemini": "gemini-2.0-flash", "gemini-pro": "gemini-2.0-flash",
    }
    return MODEL_MAP.get(base_model, "gpt-4o-mini")
