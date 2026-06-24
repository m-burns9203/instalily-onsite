"""The enrichment unit of work: research → structure → validate.

``Enricher.enrich(lead)`` returns a normalized dict ready to persist. In mock
mode it produces deterministic, realistic output derived from the lead's own
facts (no network, no spend) so the pipeline and UI are fully demonstrable.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings, get_settings
from . import prompts
from .clients import AIClients

logger = logging.getLogger(__name__)


class Enricher:
    def __init__(
        self, settings: Settings | None = None, clients: AIClients | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self._clients = clients

    @property
    def clients(self) -> AIClients:
        if self._clients is None:
            self._clients = AIClients(self.settings)
        return self._clients

    def enrich(self, lead: dict[str, Any]) -> dict[str, Any]:
        if self.settings.effective_mock_mode:
            return _mock_enrichment(lead)

        # Stage 1: live web research (Perplexity).
        research_prompt = prompts.RESEARCH_PROMPT.format(
            name=lead.get("name", ""),
            city=lead.get("city", ""),
            state=lead.get("state", ""),
            zip_code=lead.get("zip_code", ""),
            website=lead.get("website") or "unknown",
            certification=lead.get("certification") or "none",
        )
        research_text, citations = self.clients.research(research_prompt)

        # Stage 2: structure into a strict JSON brief (OpenAI JSON mode).
        structuring_prompt = prompts.build_structuring_prompt(lead, research_text)
        raw_json = self.clients.structure(
            prompts.STRUCTURING_SYSTEM, structuring_prompt
        )
        data = _safe_json(raw_json)

        # Merge citations from research into the brief's sources.
        sources = list(dict.fromkeys([*data.get("sources", []), *citations]))
        data["sources"] = sources
        data["model_version"] = (
            f"{self.settings.perplexity_model}+{self.settings.openai_model}"
        )
        return _normalize_enrichment(data)


def _safe_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Tolerate models that wrap JSON in prose/fences.
        start, end = raw.find("{"), raw.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        logger.warning("Enrichment returned unparseable JSON; storing minimal brief.")
        return {}


def _normalize_enrichment(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce model output into the exact shape the repository expects."""
    def _as_list(v: Any) -> list:
        if isinstance(v, list):
            return v
        if v in (None, ""):
            return []
        return [v]

    score = data.get("lead_score")
    try:
        score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        score = None

    return {
        "summary": data.get("summary"),
        "estimated_size": data.get("estimated_size"),
        "years_in_business": data.get("years_in_business"),
        "specialties": _as_list(data.get("specialties")),
        "service_areas": _as_list(data.get("service_areas")),
        "recent_activity": data.get("recent_activity"),
        "recommended_products": _as_list(data.get("recommended_products")),
        "talking_points": _as_list(data.get("talking_points")),
        "buying_signals": _as_list(data.get("buying_signals")),
        "outreach_strategy": data.get("outreach_strategy"),
        "decision_makers": _as_list(data.get("decision_makers")),
        "sources": _as_list(data.get("sources")),
        "model_version": data.get("model_version", "mock"),
        "lead_score": score,
    }


# --------------------------------------------------------------------------
# Deterministic mock enrichment — realistic output from the lead's own facts.
# --------------------------------------------------------------------------
def _mock_enrichment(lead: dict[str, Any]) -> dict[str, Any]:
    name = lead.get("name", "This contractor")
    cert = lead.get("certification")
    rating = lead.get("rating") or 0
    reviews = lead.get("review_count") or 0
    city = lead.get("city", "the area")
    is_elite = cert == "Master Elite"

    size = "Mid-size (11-50)" if reviews > 150 else "Small (1-10)"
    if reviews > 300:
        size = "Large (50+)"

    specialties = ["Asphalt shingle", "Roof replacement", "Storm repair"]
    if is_elite:
        specialties += ["Architectural shingles", "Premium underlayment systems"]
    if "commercial" in name.lower() or "flat" in name.lower():
        specialties = ["Flat / TPO / EPDM", "Commercial re-roofing", "Roof coatings"]

    products = [
        {
            "product": "GAF Timberline HDZ architectural shingles",
            "reason": f"{name} runs high residential volume; premium shingles lift margin per job.",
        },
        {
            "product": "Underlayment + ventilation accessories bundle",
            "reason": "Attach-rate products that pull through with every shingle order.",
        },
    ]
    if is_elite:
        products.append(
            {
                "product": "Extended-warranty eligible system components",
                "reason": "Master Elite status lets them sell GAF's strongest warranties — stock the full system.",
            }
        )

    talking_points = [
        f"Congratulate them on their {rating}★ rating across {reviews} reviews — clear demand signal.",
        f"Lead with reliable local availability and next-day delivery to {city} job sites.",
        "Offer contractor-tier pricing + a co-branded marketing rebate to win wallet share.",
    ]
    if is_elite:
        talking_points.append(
            "Position the full GAF system so they can offer the Golden Pledge warranty."
        )

    buying_signals = []
    if rating >= 4.5 and reviews >= 150:
        buying_signals.append("High review velocity → steady, growing job volume.")
    if is_elite:
        buying_signals.append("Master Elite certification → committed GAF buyer, expandable share.")
    if (lead.get("distance_miles") or 99) < 5:
        buying_signals.append("Close to distribution hub → low delivery cost, easy to service.")
    if not buying_signals:
        buying_signals.append("Established local presence worth a relationship-building call.")

    score = _mock_score(lead)

    return {
        "summary": (
            f"{name} is a {cert or 'local'} roofing contractor based in {city} with a "
            f"{rating}★ reputation ({reviews} reviews). A strong fit for a "
            f"distributor relationship given their {size.split(' ')[0].lower()} scale and steady residential demand."
        ),
        "estimated_size": size,
        "years_in_business": "10+ years" if is_elite else "5-10 years",
        "specialties": specialties,
        "service_areas": [city, f"Greater {lead.get('state', '')} metro".strip()],
        "recent_activity": (
            f"Consistently strong recent reviews ({reviews} total) indicate active, ongoing project work."
        ),
        "recommended_products": products,
        "talking_points": talking_points,
        "buying_signals": buying_signals,
        "outreach_strategy": (
            f"Open with the owner/operations lead at {name}. Lead with availability + "
            "contractor pricing, then propose a standing weekly order to lock in share."
        ),
        "decision_makers": [
            {
                "name": "Unknown",
                "title": "Owner / President",
                "rationale": "Final say on supplier relationships at a contractor this size.",
                "linkedin_url": None,
            },
            {
                "name": "Unknown",
                "title": "Operations / Purchasing Manager",
                "rationale": "Owns day-to-day material ordering and delivery scheduling.",
                "linkedin_url": None,
            },
        ],
        "sources": [lead.get("source_url")] if lead.get("source_url") else [],
        "model_version": "mock",
        "lead_score": score,
    }


def _mock_score(lead: dict[str, Any]) -> int:
    """Mirror scoring.compute_lead_score so mock + DB-stored scores agree."""
    from ..scoring import compute_lead_score

    return compute_lead_score(lead)
