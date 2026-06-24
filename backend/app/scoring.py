"""Lead scoring - a transparent, explainable heuristic.

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


def _raw_components(lead: dict[str, Any]) -> list[dict[str, Any]]:
    """The per-factor contributions (unrounded) that make up a lead score.

    Returned as data so the same definition powers both the numeric score and
    the explainable breakdown the UI shows reps - there is exactly one source
    of truth for "why is this lead an 87?".
    """
    rating = lead.get("rating") or 0
    reviews = lead.get("review_count") or 0
    distance = lead.get("distance_miles")
    cert = lead.get("certification")
    has_phone = bool(lead.get("phone"))
    has_website = bool(lead.get("website"))

    # Certification: proxy for GAF commitment + ability to sell premium systems.
    cert_pts = float(_CERT_POINTS.get(cert, 0))
    # Reputation: rating × volume of reviews = sustained, real demand.
    rating_pts = min(20.0, (rating / 5.0) * 20.0)
    reviews_pts = min(20.0, (reviews / 300.0) * 20.0)
    # Proximity: closer contractors are cheaper to serve and easier to win.
    proximity_pts = (
        max(0.0, 15.0 * (1.0 - min(distance, 25.0) / 25.0))
        if distance is not None
        else 0.0
    )
    # Reachability: a lead with phone + website is actionable today.
    reachable_pts = (7.5 if has_phone else 0.0) + (7.5 if has_website else 0.0)

    reach_detail = ", ".join(
        x for x in ("phone" if has_phone else None, "website" if has_website else None) if x
    ) or "none on file"

    return [
        {"label": "Certification", "points": cert_pts, "max": 30,
         "detail": cert or "Uncertified"},
        {"label": "Rating", "points": rating_pts, "max": 20,
         "detail": f"{rating}/5" if rating else "No rating"},
        {"label": "Review volume", "points": reviews_pts, "max": 20,
         "detail": f"{reviews} reviews"},
        {"label": "Proximity", "points": proximity_pts, "max": 15,
         "detail": f"{distance:.1f} mi" if distance is not None else "Distance unknown"},
        {"label": "Reachability", "points": reachable_pts, "max": 15,
         "detail": reach_detail},
    ]


def score_components(lead: dict[str, Any]) -> list[dict[str, Any]]:
    """Display-ready score breakdown (points rounded to whole numbers)."""
    return [
        {**c, "points": int(round(c["points"]))} for c in _raw_components(lead)
    ]


def compute_lead_score(lead: dict[str, Any]) -> int:
    # Sum the rounded display components so the score always equals the sum of
    # the factor bars the UI shows the rep - no off-by-one between ring + bars.
    score = sum(c["points"] for c in score_components(lead))
    return int(max(0, min(100, score)))


def score_band(score: int | None) -> str:
    if score is None:
        return "unscored"
    if score >= 80:
        return "hot"
    if score >= 60:
        return "warm"
    return "nurture"
