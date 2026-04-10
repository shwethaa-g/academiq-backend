"""
AcademIQ Risk Scoring Engine
PRD Section 4 — Weighted multi-signal model

Signals (6 total):
  1. Attendance            weight 25
  2. Grade average         weight 25
  3. LMS engagement        weight 20
  4. Assignment completion weight 15
  5. Sentiment             weight 10
  6. Missed surveys        weight  5
                          ─────────
                    Total weight 100

Score range: 0–100 (higher = more at risk)
Tiers:
  GREEN  < 45
  AMBER  45–69
  RED    ≥ 70
"""

from __future__ import annotations
from dataclasses import dataclass, field
from app.models.schemas import RiskSignals
from app.core.config import get_settings

settings = get_settings()

# ── Weights ──────────────────────────────────────────────────────────────────

WEIGHTS = {
    "attendance":    25,
    "grade":         25,
    "lms":           20,
    "assignments":   15,
    "sentiment":     10,
    "surveys":        5,
}

# ── Per-signal scoring helpers ───────────────────────────────────────────────


def _score_attendance(pct: float) -> float:
    """0% attendance → 100 risk contribution. 100% → 0."""
    pct = max(0.0, min(100.0, pct))
    return 100.0 - pct


def _score_grade(avg: float) -> float:
    """Grade 0 → 100 risk. Grade 100 → 0 risk."""
    avg = max(0.0, min(100.0, avg))
    return 100.0 - avg


def _score_lms(logins_per_week: int) -> float:
    """
    Expected ≥ 7 logins/week = 0 risk.
    0 logins = 100 risk. Linear between 0-7, capped.
    """
    logins = max(0, logins_per_week)
    if logins >= 7:
        return 0.0
    return round((1 - logins / 7) * 100, 2)


def _score_assignments(completion_pct: float) -> float:
    """100% completion → 0 risk. 0% → 100 risk."""
    pct = max(0.0, min(100.0, completion_pct))
    return 100.0 - pct


def _score_sentiment(score: float) -> float:
    """
    Sentiment score from Claude: -1.0 (very negative) to +1.0 (very positive).
    Maps to risk: -1.0 → 100, 0.0 → 50, +1.0 → 0.
    """
    score = max(-1.0, min(1.0, score))
    return round((1.0 - score) / 2.0 * 100, 2)


def _score_missed_surveys(missed: int) -> float:
    """
    0 missed → 0 risk.
    1 missed → 33 risk.
    2 missed → 66 risk.
    3+ missed → 100 risk (cap).
    """
    missed = max(0, missed)
    return min(100.0, missed * 33.33)


# ── Main scorer ──────────────────────────────────────────────────────────────

@dataclass
class RiskScoreResult:
    total_score: float
    tier: str
    breakdown: dict = field(default_factory=dict)


def compute_risk_score(signals: RiskSignals) -> RiskScoreResult:
    """
    Compute weighted risk score from 6 input signals.
    Returns total 0-100 score, tier string, and per-signal breakdown.
    """
    raw = {
        "attendance":  _score_attendance(signals.attendance_pct),
        "grade":       _score_grade(signals.grade_avg),
        "lms":         _score_lms(signals.lms_logins_week),
        "assignments": _score_assignments(signals.assignment_completion_pct),
        "sentiment":   _score_sentiment(signals.sentiment_score),
        "surveys":     _score_missed_surveys(signals.missed_surveys),
    }

    weighted = {k: round(raw[k] * WEIGHTS[k] / 100, 3) for k in raw}
    total = round(sum(weighted.values()), 2)

    # Hard cap at 100
    total = min(100.0, total)

    tier = _tier(total)

    breakdown = {
        k: {
            "raw_score": raw[k],
            "weight": WEIGHTS[k],
            "weighted_contribution": weighted[k],
        }
        for k in raw
    }

    return RiskScoreResult(total_score=total, tier=tier, breakdown=breakdown)


def _tier(score: float) -> str:
    red_threshold = settings.RISK_RED_THRESHOLD
    amber_threshold = settings.RISK_AMBER_THRESHOLD
    if score >= red_threshold:
        return "RED"
    if score >= amber_threshold:
        return "AMBER"
    return "GREEN"
