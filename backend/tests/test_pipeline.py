"""End-to-end pipeline tests against an isolated in-memory database.

These run entirely offline (mock mode) and validate the parts most likely to
break in production: idempotent upserts, the enrichment write path, scoring,
and the full scrape→enrich→store flow.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    """Reset to a clean schema before each test (isolated test DB from conftest)."""
    import app.models  # noqa: F401 — ensure models register on Base
    from app.db import Base, engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    import app.db as db_module

    return db_module


def test_scraper_returns_seed_in_mock_mode():
    from app.config import get_settings
    from app.scraper.gaf import GafScraper

    get_settings.cache_clear()
    records = GafScraper().scrape("10013", 25)
    assert len(records) >= 10
    assert all(r["source_key"] for r in records)
    assert all(r["name"] for r in records)


def test_scoring_is_bounded_and_ordered():
    from app.scoring import compute_lead_score, score_band

    strong = {
        "certification": "Master Elite", "rating": 4.9, "review_count": 400,
        "distance_miles": 0.5, "phone": "x", "website": "y",
    }
    weak = {"certification": None, "rating": 3.0, "review_count": 5,
            "distance_miles": 24}
    s_strong, s_weak = compute_lead_score(strong), compute_lead_score(weak)
    assert 0 <= s_weak < s_strong <= 100
    assert score_band(s_strong) in {"hot", "warm"}


def test_full_pipeline_enriches_and_is_idempotent(db, monkeypatch):
    from app.config import get_settings
    from app.models import EnrichmentStatus, Lead
    from app.pipeline.orchestrator import PipelineOrchestrator

    get_settings.cache_clear()
    orch = PipelineOrchestrator()

    result1 = orch.run_sync(zip_code="10013", radius=25)
    assert result1.discovered >= 10
    assert result1.new == result1.discovered  # first run: all new
    assert result1.enriched == result1.discovered
    assert result1.failed == 0

    Session = sessionmaker(bind=db.engine)
    with Session() as s:
        leads = s.scalars(select(Lead)).all()
        assert len(leads) == result1.discovered
        assert all(l.enrichment_status == EnrichmentStatus.ENRICHED for l in leads)
        assert all(l.enrichment is not None for l in leads)
        assert all(l.lead_score is not None for l in leads)
        # Enrichment produced decision-makers + a summary.
        sample = leads[0]
        assert sample.enrichment.summary
        assert len(sample.decision_makers) >= 1

    # Second run must NOT duplicate leads (idempotent upsert by source_key).
    result2 = orch.run_sync(zip_code="10013", radius=25)
    assert result2.new == 0
    with Session() as s:
        assert len(s.scalars(select(Lead)).all()) == result1.discovered


def test_enrichment_failure_is_isolated(db, monkeypatch):
    """A failing lead is marked FAILED and does not abort the whole run."""
    from app.config import get_settings
    from app.enrichment.enricher import Enricher
    from app.models import EnrichmentStatus, Lead
    from app.pipeline.orchestrator import PipelineOrchestrator

    get_settings.cache_clear()

    calls = {"n": 0}
    original = Enricher.enrich

    def flaky(self, lead):
        calls["n"] += 1
        if calls["n"] == 1:  # fail exactly one lead
            raise RuntimeError("simulated provider error")
        return original(self, lead)

    monkeypatch.setattr(Enricher, "enrich", flaky)

    result = PipelineOrchestrator().run_sync(zip_code="10013", radius=25)
    assert result.failed == 1
    assert result.enriched == result.discovered - 1

    Session = sessionmaker(bind=db.engine)
    with Session() as s:
        failed = s.scalars(
            select(Lead).where(Lead.enrichment_status == EnrichmentStatus.FAILED)
        ).all()
        assert len(failed) == 1
