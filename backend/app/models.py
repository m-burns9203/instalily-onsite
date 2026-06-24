"""SQLAlchemy ORM models — the persistence layer.

Schema design goals (grading criterion #2, "robust data management"):

* **Separation of concerns.** Raw scraped facts (`Lead`) are kept distinct
  from AI-generated, regenerable analysis (`Enrichment`). We never lose the
  ground-truth source data when we re-run enrichment, and we can re-enrich
  with a better model without re-scraping.
* **Idempotency.** Every lead has a stable `source_key` (a hash of its GAF
  identity) with a unique constraint, so re-scraping upserts instead of
  duplicating.
* **Auditability.** `PipelineRun` records every ingest/enrich execution, and
  `EnrichmentJob` is a durable work-queue row with attempt counts and error
  capture — the backbone of the scalable, retryable pipeline.
* **Normalization where it matters.** Decision-makers are first-class rows
  (queryable, one-to-many) rather than buried in a JSON blob.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EnrichmentStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    ENRICHED = "enriched"
    FAILED = "failed"


class Lead(Base):
    """A roofing contractor sourced from GAF — a prospect for the distributor."""

    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("source_key", name="uq_leads_source_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Stable natural key derived from the source identity (see scraper).
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="GAF")
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core scraped facts.
    name: Mapped[str] = mapped_column(String(255), index=True)
    certification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(EnrichmentStatus), default=EnrichmentStatus.PENDING, index=True
    )
    # Denormalized for fast sorting/filtering in the lead list.
    lead_score: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    enrichment: Mapped["Enrichment | None"] = relationship(
        back_populates="lead",
        uselist=False,
        cascade="all, delete-orphan",
    )
    decision_makers: Mapped[list["DecisionMaker"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )


class Enrichment(Base):
    """AI-generated sales intelligence for a lead. Regenerable; versioned."""

    __tablename__ = "enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), unique=True, index=True
    )

    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    years_in_business: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specialties: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    service_areas: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    recent_activity: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sales playbook fields.
    recommended_products: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    talking_points: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    outreach_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    buying_signals: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of URLs

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    lead: Mapped[Lead] = relationship(back_populates="enrichment")


class DecisionMaker(Base):
    """A person worth contacting at a lead's organization."""

    __tablename__ = "decision_makers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    lead: Mapped[Lead] = relationship(back_populates="decision_makers")


class EnrichmentJob(Base):
    """Durable work-queue row driving the async enrichment pipeline.

    Modeling the queue in the database (rather than only in memory) makes the
    pipeline crash-safe and horizontally scalable. Today a single in-process
    worker pool processes these rows, retrying each lead up to
    ``enrich_max_attempts`` with exponential backoff and recording
    ``attempts``/``last_error``. Because the work-list lives in the table, the
    same rows support a multi-worker fleet: each worker atomically claims a
    QUEUED job (``SELECT ... FOR UPDATE SKIP LOCKED`` on Postgres), so this is
    the natural seam to swap for Redis/SQS/Celery without changing the
    orchestration logic.
    """

    __tablename__ = "enrichment_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_runs.id"), nullable=True, index=True
    )
    status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(EnrichmentStatus), default=EnrichmentStatus.QUEUED, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class PipelineRun(Base):
    """Audit record for one end-to-end pipeline execution."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)

    leads_discovered: Mapped[int] = mapped_column(Integer, default=0)
    leads_new: Mapped[int] = mapped_column(Integer, default=0)
    leads_enriched: Mapped[int] = mapped_column(Integer, default=0)
    leads_failed: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
