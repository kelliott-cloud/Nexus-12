"""Dynamic prompt assembly from agent config, skills, guardrails, and context."""
from typing import Dict, Any
from agent_skill_definitions import build_skill_prompt_fragment


async def build_agent_prompt(db, agent_config: Dict[str, Any], workspace_id: str, channel_id: str) -> str:
    """Assemble the full system prompt for an agent from all its configuration."""
    parts = [agent_config.get("system_prompt", "")]

    skills = agent_config.get("skills") or []
    if skills:
        fragment = build_skill_prompt_fragment(skills)
        if fragment:
            parts.append(fragment)

    personality = agent_config.get("personality") or {}
    if personality:
        tone = personality.get("tone", "balanced")
        verbosity = personality.get("verbosity", "balanced")
        risk = personality.get("risk_tolerance", "moderate")
        collab = personality.get("collaboration_style", "contributor")
        parts.append(f"\n[PERSONALITY] Tone: {tone} | Verbosity: {verbosity} | Risk tolerance: {risk} | Style: {collab}")

    guardrails = agent_config.get("guardrails") or {}
    if guardrails:
        gp = []
        if guardrails.get("require_citations"):
            gp.append("Always cite sources for factual claims.")
        if guardrails.get("require_confidence"):
            gp.append("Include [CONFIDENCE: X%] at the end of every response.")
        if guardrails.get("max_response_length"):
            gp.append(f"Keep responses under {guardrails['max_response_length']} characters.")
        if guardrails.get("escalation_threshold"):
            gp.append(f"If your confidence is below {int(guardrails['escalation_threshold'] * 100)}%, explicitly say you're uncertain and suggest escalating.")
        forbidden = guardrails.get("forbidden_topics") or []
        if forbidden:
            gp.append(f"NEVER discuss: {', '.join(forbidden)}")
        if gp:
            parts.append("\n=== GUARDRAILS ===\n" + "\n".join(f"- {g}" for g in gp) + "\n=== END GUARDRAILS ===")

    denied = agent_config.get("denied_tools") or []
    if denied:
        parts.append(f"\n[TOOL RESTRICTIONS] You are NOT allowed to use: {', '.join(denied)}.")

    # RAG: Inject relevant knowledge from agent's training data
    agent_id = agent_config.get("agent_id")
    if agent_id and db:
        try:
            from agent_knowledge_retrieval import retrieve_training_knowledge
            last_msg = await db.messages.find_one(
                {"channel_id": channel_id, "sender_type": "user"},
                {"_id": 0, "content": 1},
                sort=[("created_at", -1)]
            )
            query = last_msg.get("content", "") if last_msg else ""
            if query:
                training_config = agent_config.get("training") or {}
                training_ctx = await retrieve_training_knowledge(
                    db, agent_id, query,
                    max_chunks=training_config.get("max_chunks", 8),
                    max_tokens=training_config.get("knowledge_token_budget", 3000),
                    min_relevance=training_config.get("min_relevance_score", 0.3),
                    strategy=training_config.get("retrieval_strategy", "semantic"),
                )
                if training_ctx:
                    parts.append(training_ctx)
        except Exception as _e:
            import logging; logging.getLogger("agent_prompt_builder").warning(f"Suppressed: {_e}")  # Don't fail prompt assembly if knowledge retrieval fails

    return "\n".join(parts)
