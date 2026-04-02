"""Confidence Scoring — Self-evaluated confidence on every agent response.

Parses confidence signals from agent responses and stores them.
Agents are prompted to include a confidence level in their responses.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Confidence indicators in agent text
HIGH_CONFIDENCE = ["I'm confident", "definitely", "certainly", "clearly", "without doubt", "I can confirm"]
MEDIUM_CONFIDENCE = ["I think", "I believe", "likely", "probably", "most likely", "should work"]
LOW_CONFIDENCE = ["I'm not sure", "uncertain", "might", "possibly", "I'd guess", "not certain", "unclear"]
HEDGING = ["however", "but", "although", "on the other hand", "it depends", "that said"]


def estimate_confidence(response_text: str) -> dict:
    """Estimate confidence level from an agent's response text.
    
    Returns:
        {"score": 0.0-1.0, "level": "high"|"medium"|"low", "signals": [...]}
    """
    if not response_text:
        return {"score": 0.5, "level": "medium", "signals": []}
    
    lower = response_text.lower()
    signals = []
    
    # Check for explicit confidence markers
    high_count = sum(1 for p in HIGH_CONFIDENCE if p.lower() in lower)
    med_count = sum(1 for p in MEDIUM_CONFIDENCE if p.lower() in lower)
    low_count = sum(1 for p in LOW_CONFIDENCE if p.lower() in lower)
    hedge_count = sum(1 for p in HEDGING if p.lower() in lower)
    
    if high_count > 0:
        signals.append(f"{high_count} high-confidence phrases")
    if low_count > 0:
        signals.append(f"{low_count} low-confidence phrases")
    if hedge_count > 0:
        signals.append(f"{hedge_count} hedging phrases")
    
    # Check for explicit confidence declaration [CONFIDENCE: X%]
    conf_match = re.search(r'\[CONFIDENCE:\s*(\d+)%?\]', response_text, re.IGNORECASE)
    if conf_match:
        explicit = int(conf_match.group(1)) / 100
        signals.append(f"explicit: {int(explicit*100)}%")
        return {"score": round(explicit, 2), "level": _level(explicit), "signals": signals}
    
    # Code blocks = higher confidence (concrete output)
    code_blocks = response_text.count("```")
    if code_blocks >= 2:
        signals.append("contains code")
        high_count += 1
    
    # Questions = lower confidence
    question_count = response_text.count("?")
    if question_count >= 3:
        signals.append(f"{question_count} questions")
        low_count += 1
    
    # Calculate score
    score = 0.5
    score += high_count * 0.12
    score -= low_count * 0.15
    score -= hedge_count * 0.05
    score += med_count * 0.03
    
    # Length bonus (longer = more detailed = slightly higher confidence)
    if len(response_text) > 1000:
        score += 0.05
    
    score = max(0.1, min(1.0, score))
    
    return {"score": round(score, 2), "level": _level(score), "signals": signals}


def _level(score):
    if score >= 0.75:
        return "high"
    elif score >= 0.45:
        return "medium"
    return "low"


# Prompt injection to encourage confidence signals
CONFIDENCE_PROMPT = """
When responding, include a confidence indicator at the end of your message:
[CONFIDENCE: X%] where X is your self-assessed confidence (0-100).
Consider: how certain are you about the accuracy and completeness of your response?
"""
