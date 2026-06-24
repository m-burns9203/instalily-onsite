"""Pydantic schemas for API responses. Decouples wire format from ORM models."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from .models import DecisionMaker, Enrichment, Lead
from .scoring import score_band


def _loads(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return []


class DecisionMakerOut(BaseModel):
    name: str | None = None
    title: str | None = None
    rationale: str | None = None
    linkedin_url: str | None = None

    @classmethod
    def from_model(cls, dm: DecisionMaker) -> "DecisionMakerOut":
        return cls(
            name=dm.name, title=dm.title, rationale=dm.rationale,
            linkedin_url=dm.linkedin_url,
        )


class EnrichmentOut(BaseModel):
    summary: str | None = None
    estimated_size: str | None = None
    years_in_business: str | None = None
    specialties: list[str] = []
    service_areas: list[str] = []
    recent_activity: str | None = None
    recommended_products: list[dict] = []
    talking_points: list[str] = []
    buying_signals: list[str] = []
    outreach_strategy: str | None = None
    sources: list[str] = []
    model_version: str | None = None

    @classmethod
    def from_model(cls, e: Enrichment) -> "EnrichmentOut":
        return cls(
            summary=e.summary,
            estimated_size=e.estimated_size,
            years_in_business=e.years_in_business,
            specialties=_loads(e.specialties),
            service_areas=_loads(e.service_areas),
            recent_activity=e.recent_activity,
            recommended_products=_loads(e.recommended_products),
            talking_points=_loads(e.talking_points),
            buying_signals=_loads(e.buying_signals),
            outreach_strategy=e.outreach_strategy,
            sources=[s for s in _loads(e.sources) if s],
            model_version=e.model_version,
        )


class LeadSummary(BaseModel):
    id: int
    name: str
    certification: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    distance_miles: float | None = None
    rating: float | None = None
    review_count: int | None = None
    phone: str | None = None
    website: str | None = None
    lead_score: int | None = None
    score_band: str
    enrichment_status: str
    summary: str | None = None
    top_signal: str | None = None

    @classmethod
    def from_model(cls, lead: Lead) -> "LeadSummary":
        e = lead.enrichment
        signals = _loads(e.buying_signals) if e else []
        return cls(
            id=lead.id,
            name=lead.name,
            certification=lead.certification,
            city=lead.city,
            state=lead.state,
            zip_code=lead.zip_code,
            distance_miles=lead.distance_miles,
            rating=lead.rating,
            review_count=lead.review_count,
            phone=lead.phone,
            website=lead.website,
            lead_score=lead.lead_score,
            score_band=score_band(lead.lead_score),
            enrichment_status=lead.enrichment_status.value,
            summary=e.summary if e else None,
            top_signal=signals[0] if signals else None,
        )


class LeadDetail(LeadSummary):
    source: str | None = None
    source_url: str | None = None
    address: str | None = None
    enrichment: EnrichmentOut | None = None
    decision_makers: list[DecisionMakerOut] = []

    @classmethod
    def from_model(cls, lead: Lead) -> "LeadDetail":
        base = LeadSummary.from_model(lead).model_dump()
        return cls(
            **base,
            source=lead.source,
            source_url=lead.source_url,
            address=lead.address,
            enrichment=EnrichmentOut.from_model(lead.enrichment)
            if lead.enrichment
            else None,
            decision_makers=[
                DecisionMakerOut.from_model(dm) for dm in lead.decision_makers
            ],
        )


class LeadListOut(BaseModel):
    total: int
    items: list[LeadSummary]


class StatsOut(BaseModel):
    total_leads: int
    enriched: int
    pending: int
    hot_leads: int
    avg_score: float | None
    by_certification: dict[str, int]


class RunRequest(BaseModel):
    zip_code: str | None = None
    radius: int | None = None
    reenrich: bool = False


class RunOut(BaseModel):
    run_id: int
    discovered: int
    new: int
    enriched: int
    failed: int
    mock_mode: bool
