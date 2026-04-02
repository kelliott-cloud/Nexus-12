from nexus_utils import now_iso
"""Real AI-powered Agent Evaluator — Assesses agent skills using actual AI calls.

Sends test prompts per skill, evaluates responses, computes scores,
awards badges via agent_certification.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger("agent_evaluator")


async def run_real_assessment(
    db, workspace_id: str, agent_id: str, skill_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Run AI-powered skill assessment for an agent.

    For each configured skill, sends the skill's assessment prompt to the agent,
    evaluates the response quality, and computes a score.
    """
    from agent_skill_definitions import BUILTIN_SKILLS

    agent = await db.nexus_agents.find_one(
        {"agent_id": agent_id, "workspace_id": workspace_id},
        {"_id": 0}
    )
    if not agent:
        return {"error": "Agent not found"}

    configured_skills = agent.get("skills") or []
    if not configured_skills:
        return {"error": "No skills configured"}

    # Determine which skills to assess
    if skill_ids:
        to_assess = [s for s in configured_skills if s.get("skill_id") in skill_ids]
    else:
        to_assess = configured_skills

    # Get the AI key for this agent
    from collaboration_core import get_ai_key_for_agent
    # Use workspace creator as the user for evaluation
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "created_by": 1})
    user_id = ws.get("created_by", "") if ws else ""
    base_model = agent.get("base_model", "claude")
    api_key, key_source = await get_ai_key_for_agent(user_id, workspace_id, base_model)

    skill_scores = {}
    assessment_id = f"eval_{uuid.uuid4().hex[:12]}"

    for skill_config in to_assess[:10]:  # Limit to 10 skills per assessment
        skill_id = skill_config.get("skill_id")
        skill_def = BUILTIN_SKILLS.get(skill_id)
        if not skill_def:
            continue

        assessment = skill_def.get("assessment") or {}
        test_prompt = assessment.get("prompt", f"Demonstrate your {skill_id.replace('_', ' ')} expertise.")
        criteria = assessment.get("criteria", ["completeness", "accuracy", "depth"])

        # Build system prompt for the agent being evaluated
        from agent_prompt_builder import build_agent_prompt
        try:
            system_prompt = await build_agent_prompt(db, agent, workspace_id, "eval_channel")
        except Exception:
            system_prompt = agent.get("system_prompt", "You are a helpful AI assistant.")

        score = 0
        response_text = ""

        if api_key:
            try:
                from ai_providers import call_ai_direct
                response_text = await call_ai_direct(
                    base_model, api_key, system_prompt, test_prompt,
                    workspace_id=workspace_id, db=db
                )

                # Evaluate the response using a judge prompt
                judge_prompt = (
                    "You are an expert evaluator. Rate the following AI response on a scale of 0-100 based on these criteria: "
                    f"{', '.join(criteria)}.\n\n"
                    f"Task: {test_prompt}\n\n"
                    f"Response:\n{response_text[:2000]}\n\n"
                    "Reply with ONLY a number between 0 and 100."
                )
                judge_response = await call_ai_direct(
                    base_model, api_key,
                    "You are a strict but fair evaluator. Reply with only a number 0-100.",
                    judge_prompt,
                    workspace_id=workspace_id, db=db
                )
                # Extract score
                import re
                numbers = re.findall(r'\d+', judge_response)
                if numbers:
                    score = min(100, max(0, int(numbers[0])))
                else:
                    score = 50  # Default if parsing fails

            except Exception as e:
                logger.warning(f"AI evaluation failed for {skill_id}: {e}")
                # Fall back to heuristic scoring
                score = _heuristic_score(response_text, skill_id)
        else:
            # No API key — use heuristic scoring
            score = _heuristic_score("", skill_id)

        skill_scores[skill_id] = {
            "score": score,
            "response_preview": response_text[:200] if response_text else "",
            "criteria": criteria,
            "assessed_at": now_iso(),
        }

        # Update agent_skills with assessment score
        await db.agent_skills.update_one(
            {"workspace_id": workspace_id, "agent_key": agent_id, "skill": skill_id},
            {
                "$set": {
                    "assessment_score": score,
                    "last_assessed": now_iso(),
                    "proficiency": score,
                    "level": _score_to_level(score),
                },
                "$setOnInsert": {"created_at": now_iso()},
            },
            upsert=True,
        )

    # Compute overall score
    # Apply training quality boost — agents with deeper training data get score bonus
    try:
        training_config = agent.get("training") or {}
        total_chunks = training_config.get("total_chunks", 0)
        if total_chunks > 0:
            from agent_training_crawler import SKILL_TOPIC_SUGGESTIONS
            for sid in list(skill_scores.keys()):
                suggested_topics = SKILL_TOPIC_SUGGESTIONS.get(sid, [])
                if suggested_topics:
                    covered = await db.agent_knowledge.count_documents({
                        "agent_id": agent_id, "flagged": {"$ne": True},
                        "topic": {"$in": suggested_topics}
                    })
                    coverage_ratio = min(covered / max(len(suggested_topics) * 3, 1), 1.0)
                    boost = round(coverage_ratio * 8)  # Up to +8 points
                    if boost > 0:
                        old_score = skill_scores[sid]["score"]
                        skill_scores[sid]["score"] = min(100, old_score + boost)
                        skill_scores[sid]["training_boost"] = boost
    except Exception as tb_err:
        logger.debug(f"Training boost calc failed: {tb_err}")

    # --- Dojo Session Assessment Evidence ---
    try:
        for skill_config in to_assess:
            skill_id = skill_config.get("skill_id")
            dojo_sessions = await db.dojo_sessions.find(
                {"workspace_id": workspace_id, "agents.agent_id": agent_id, "status": "completed"},
                {"_id": 0, "synthetic_data": 1, "scenario_id": 1}
            ).limit(10).to_list(10)
            for ds in dojo_sessions:
                scenario_id = ds.get("scenario_id", "")
                try:
                    from dojo_scenarios import get_scenario
                    scenario = get_scenario(scenario_id)
                except (ImportError, Exception):
                    scenario = None
                if scenario and skill_id in scenario.get("skill_alignment", []):
                    quality = (ds.get("synthetic_data") or {}).get("quality_avg", 0)
                    if quality > 0.6:
                        current = skill_scores.get(skill_id, {}).get("score", 0)
                        dojo_bonus = min(10, int(quality * 15))
                        skill_scores[skill_id] = {
                            **skill_scores.get(skill_id, {}),
                            "score": min(100, current + dojo_bonus),
                            "dojo_evidence": True,
                            "dojo_sessions_count": len(dojo_sessions),
                        }
    except Exception as e:
        logger.debug(f"Dojo assessment evidence check: {e}")

    overall = round(sum(s["score"] for s in skill_scores.values()) / max(len(skill_scores), 1), 1)

    # Update agent evaluation record
    await db.nexus_agents.update_one(
        {"agent_id": agent_id},
        {"$set": {
            "evaluation.overall_score": overall,
            "evaluation.skill_scores": skill_scores,
            "evaluation.last_assessed": now_iso(),
            "evaluation.assessment_id": assessment_id,
        }}
    )

    # Award badges
    from agent_certification import check_and_award_badges
    badges = await check_and_award_badges(db, workspace_id, agent_id)

    # Store assessment record
    await db.agent_assessments.insert_one({
        "assessment_id": assessment_id,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "skill_scores": skill_scores,
        "overall_score": overall,
        "badges_awarded": badges,
        "method": "ai" if api_key else "heuristic",
        "created_at": now_iso(),
    })

    return {
        "assessment_id": assessment_id,
        "overall_score": overall,
        "skill_scores": skill_scores,
        "badges_awarded": badges,
        "method": "ai" if api_key else "heuristic",
    }


def _heuristic_score(response_text, skill_id):
    """Fallback scoring when no AI key is available."""
    if not response_text:
        return 40  # Base score for no response
    word_count = len(response_text.split())
    # Simple heuristics
    score = 40
    if word_count > 50:
        score += 10
    if word_count > 200:
        score += 10
    if word_count > 500:
        score += 10
    if any(keyword in response_text.lower() for keyword in ["example", "consider", "approach", "solution"]):
        score += 10
    if any(keyword in response_text.lower() for keyword in ["```", "code", "function", "class"]):
        score += 10
    return min(100, score)


def _score_to_level(score):
    """Convert a 0-100 score to a skill level."""
    if score >= 90:
        return "master"
    elif score >= 75:
        return "expert"
    elif score >= 55:
        return "advanced"
    elif score >= 35:
        return "intermediate"
    return "novice"
