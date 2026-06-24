"""Lead scoring — a transparent, explainable heuristic.

A rule-based score (vs. a black-box model) is the right call at this stage: it's
explainable to sales reps, deterministic, and easy to tune as the distributor
learns which signals actually convert. The weights live in one place so they can
later be calibrated against closed-won data or swapped for a learned model.

Scores roughly map to: 80-100 hot, 60-79 warm, <60 nurture.
"""
from __future__ import annotations

from typing import Any

_CERT_POINTS = {
    "Master Elite": 30,
    "President's Club": 25,
    "Certified Plus": 22,
    "Certified": 15,
}


def compute_lead_score(lead: dict[str, Any]) -> int:
    score = 0.0

    # Certification: proxy for GAF commitment + ability to sell premium systems.
    score += _CERT_POINTS.get(lead.get("certification"), 0)

    # Reputation: rating × volume of reviews = sustained, real demand.
    rating = lead.get("rating") or 0
    reviews = lead.get("review_count") or 0
    score += min(20.0, (rating / 5.0) * 20.0)
    score += min(20.0, (reviews / 300.0) * 20.0)

    # Proximity: closer contractors are cheaper to serve and easier to win.
    distance = lead.get("distance_miles")
    if distance is not None:
        score += max(0.0, 15.0 * (1.0 - min(distance, 25.0) / 25.0))

    # Completeness: a reachable lead (phone + website) is actionable today.
    if lead.get("phone"):
        score += 7.5
    if lead.get("website"):
        score += 7.5

    return int(round(max(0.0, min(100.0, score))))


def score_band(score: int | None) -> str:
    if score is None:
        return "unscored"
    if score >= 80:
        return "hot"
    if score >= 60:
        return "warm"
    return "nurture"
