"""Data-access layer.

All persistence logic lives here so the API, pipeline, and scripts share one
consistent, tested path to the database. Keeping SQL out of the route handlers
keeps the codebase maintainable and makes the storage engine swappable.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    DecisionMaker,
    Enrichment,
    EnrichmentJob,
    EnrichmentStatus,
    Lead,
    PipelineRun,
)
from .scoring import compute_lead_score

_JSON_FIELDS = (
    "specialties",
    "service_areas",
    "recommended_products",
    "talking_points",
    "buying_signals",
    "sources",
)


# -- Leads -----------------------------------------------------------------
def upsert_lead(session: Session, record: dict[str, Any]) -> tuple[Lead, bool]:
    """Insert or update a lead by its stable ``source_key``.

    Returns ``(lead, created)``. This is what makes re-scraping idempotent —
    running the pipeline twice never duplicates contractors.
    """
    existing = session.scalar(
        select(Lead).where(Lead.source_key == record["source_key"])
    )
    fields = {
        "source": record.get("source", "GAF"),
        "source_url": record.get("source_url"),
        "name": record["name"],
        "certification": record.get("certification"),
        "phone": record.get("phone"),
        "website": record.get("website"),
        "address": record.get("address"),
        "city": record.get("city"),
        "state": record.get("state"),
        "zip_code": record.get("zip_code"),
        "distance_miles": record.get("distance_miles"),
        "rating": record.get("rating"),
        "review_count": record.get("review_count"),
    }
    # Pre-compute a baseline score from scraped facts (refined after enrichment).
    baseline_score = compute_lead_score(record)

    if existing is None:
        lead = Lead(source_key=record["source_key"], lead_score=baseline_score, **fields)
        session.add(lead)
        session.flush()
        return lead, True

    for key, value in fields.items():
        setattr(existing, key, value)
    if existing.lead_score is None:
        existing.lead_score = baseline_score
    session.flush()
    return existing, False


def save_enrichment(session: Session, lead_id: int, data: dict[str, Any]) -> Enrichment:
    """Persist (or replace) the AI enrichment + decision-makers for a lead."""
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    enrichment = lead.enrichment or Enrichment(lead_id=lead_id)
    enrichment.model_version = data.get("model_version")
    enrichment.summary = data.get("summary")
    enrichment.estimated_size = data.get("estimated_size")
    enrichment.years_in_business = data.get("years_in_business")
    enrichment.recent_activity = data.get("recent_activity")
    enrichment.outreach_strategy = data.get("outreach_strategy")
    for field in _JSON_FIELDS:
        setattr(enrichment, field, json.dumps(data.get(field, [])))
    if lead.enrichment is None:
        session.add(enrichment)

    # Replace decision-makers (regenerable child rows).
    for dm in list(lead.decision_makers):
        session.delete(dm)
    for dm in data.get("decision_makers", []):
        if not isinstance(dm, dict):
            continue
        session.add(
            DecisionMaker(
                lead_id=lead_id,
                name=dm.get("name"),
                title=dm.get("title"),
                rationale=dm.get("rationale"),
                linkedin_url=dm.get("linkedin_url"),
            )
        )

    # The lead score stays the transparent, explainable heuristic
    # (see scoring.py) — we deliberately do NOT let the LLM silently override
    # it, so the score always equals the factor breakdown shown to the rep.
    lead.enrichment_status = EnrichmentStatus.ENRICHED
    session.flush()
    return enrichment


def list_leads(
    session: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    certification: str | None = None,
    min_score: int | None = None,
    sort: str = "score",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    stmt = select(Lead).options(
        selectinload(Lead.enrichment), selectinload(Lead.decision_makers)
    )
    count_stmt = select(func.count(Lead.id))

    filters = []
    if search:
        like = f"%{search.lower()}%"
        filters.append(func.lower(Lead.name).like(like))
    if status:
        filters.append(Lead.enrichment_status == EnrichmentStatus(status))
    if certification:
        filters.append(Lead.certification == certification)
    if min_score is not None:
        filters.append(Lead.lead_score >= min_score)
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    sort_col = {
        "score": Lead.lead_score.desc(),
        "name": Lead.name.asc(),
        "distance": Lead.distance_miles.asc(),
        "rating": Lead.rating.desc(),
    }.get(sort, Lead.lead_score.desc())
    stmt = stmt.order_by(sort_col).limit(limit).offset(offset)

    leads = list(session.scalars(stmt).all())
    total = session.scalar(count_stmt) or 0
    return leads, total


def get_lead(session: Session, lead_id: int) -> Lead | None:
    return session.scalar(
        select(Lead)
        .options(selectinload(Lead.enrichment), selectinload(Lead.decision_makers))
        .where(Lead.id == lead_id)
    )


def stats(session: Session) -> dict[str, Any]:
    total = session.scalar(select(func.count(Lead.id))) or 0
    enriched = (
        session.scalar(
            select(func.count(Lead.id)).where(
                Lead.enrichment_status == EnrichmentStatus.ENRICHED
            )
        )
        or 0
    )
    by_cert = dict(
        session.execute(
            select(Lead.certification, func.count(Lead.id)).group_by(
                Lead.certification
            )
        ).all()
    )
    avg_score = session.scalar(select(func.avg(Lead.lead_score)))
    hot = (
        session.scalar(select(func.count(Lead.id)).where(Lead.lead_score >= 80)) or 0
    )
    return {
        "total_leads": total,
        "enriched": enriched,
        "pending": total - enriched,
        "hot_leads": hot,
        "avg_score": round(float(avg_score), 1) if avg_score is not None else None,
        "by_certification": {str(k): v for k, v in by_cert.items()},
    }


# -- Jobs & runs -----------------------------------------------------------
def create_run(session: Session, trigger: str = "manual") -> PipelineRun:
    run = PipelineRun(trigger=trigger, status="running")
    session.add(run)
    session.flush()
    return run


def enqueue_job(session: Session, lead_id: int, run_id: int | None) -> EnrichmentJob:
    job = EnrichmentJob(
        lead_id=lead_id, run_id=run_id, status=EnrichmentStatus.QUEUED
    )
    session.add(job)
    lead = session.get(Lead, lead_id)
    if lead:
        lead.enrichment_status = EnrichmentStatus.QUEUED
    session.flush()
    return job


def latest_run(session: Session) -> PipelineRun | None:
    return session.scalar(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(1))
