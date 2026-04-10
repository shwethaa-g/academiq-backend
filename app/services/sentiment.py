"""
Sentiment analysis service.
Primary: Claude API (claude-sonnet-4-20250514)
Fallback: rule-based keyword scorer (no external call)
"""

from __future__ import annotations
import re
import logging
from typing import List

import anthropic

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Rule-based fallback ──────────────────────────────────────────────────────

POSITIVE_WORDS = {
    "great", "good", "excellent", "happy", "confident", "motivated",
    "excited", "enjoying", "fine", "okay", "well", "improving",
    "better", "positive", "clear", "understood", "helpful", "engaged",
}

NEGATIVE_WORDS = {
    "struggling", "stressed", "confused", "lost", "overwhelmed",
    "behind", "failing", "tired", "anxious", "worried", "hard",
    "difficult", "bad", "terrible", "hopeless", "depressed",
    "unmotivated", "skipped", "missed", "falling", "worse",
}


def _rule_based_sentiment(texts: List[str]) -> float:
    """Returns score -1.0 to +1.0 based on keyword matching."""
    combined = " ".join(texts).lower()
    words = re.findall(r"\b\w+\b", combined)
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


# ── Claude API scorer ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an educational wellbeing analyst. 
Analyse the student survey responses below and return ONLY a JSON object with this exact shape:
{
  "score": <float between -1.0 and 1.0>,
  "label": "<positive|neutral|negative>",
  "summary": "<one sentence summary, max 20 words>"
}

Scoring guide:
  +0.6 to +1.0 = clearly positive, engaged, confident
   0.0 to +0.5 = mildly positive or neutral
  -0.1 to -0.5 = mild concern, some struggle
  -0.6 to -1.0 = significant distress, disengagement, or risk

Return ONLY the JSON. No extra text."""


async def analyse_sentiment(survey_responses: List[str]) -> dict:
    """
    Analyse a list of free-text survey responses.
    Returns: { score: float, label: str, summary: str }
    Falls back to rule-based scorer if Claude API fails.
    """
    text_block = "\n".join(f"- {r}" for r in survey_responses if r.strip())

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text_block}],
        )

        import json
        raw = message.content[0].text.strip()
        result = json.loads(raw)

        score = float(result.get("score", 0.0))
        score = max(-1.0, min(1.0, score))

        label = result.get("label", "neutral")
        if label not in ("positive", "neutral", "negative"):
            label = _label_from_score(score)

        return {
            "score": score,
            "label": label,
            "summary": result.get("summary", ""),
            "source": "claude",
        }

    except Exception as e:
        logger.warning(f"Claude sentiment API failed, using rule-based fallback: {e}")
        score = _rule_based_sentiment(survey_responses)
        return {
            "score": score,
            "label": _label_from_score(score),
            "summary": "Sentiment estimated via keyword analysis.",
            "source": "fallback",
        }


def _label_from_score(score: float) -> str:
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"
