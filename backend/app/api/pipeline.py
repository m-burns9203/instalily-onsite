"""Pipeline trigger + run-status endpoints.

The trigger runs the orchestrator in a background task so the HTTP request
returns immediately — the UI polls ``/api/stats`` and ``/api/runs/latest`` for
progress. At production scale this handler would instead enqueue onto a
distributed queue consumed by a worker fleet.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from .. import repository
from ..config import get_settings
from ..db import get_db
from ..pipeline.orchestrator import PipelineOrchestrator
from ..schemas import RunOut, RunRequest

router = APIRouter(prefix="/api", tags=["pipeline"])
logger = logging.getLogger(__name__)

# Guard against overlapping manual triggers stepping on each other.
_run_lock = asyncio.Lock()


async def _run_pipeline(req: RunRequest) -> None:
    if _run_lock.locked():
        logger.info("Pipeline already running; skipping overlapping trigger.")
        return
    async with _run_lock:
        orchestrator = PipelineOrchestrator()
        await orchestrator.run(
            zip_code=req.zip_code,
            radius=req.radius,
            trigger="api",
            reenrich=req.reenrich,
        )


@router.post("/pipeline/run", response_model=RunOut)
async def trigger_run(
    req: RunRequest, background: BackgroundTasks, db: Session = Depends(get_db)
):
    """Kick off a pipeline run in the background; returns the prior run summary."""
    background.add_task(_run_pipeline, req)
    settings = get_settings()
    latest = repository.latest_run(db)
    return RunOut(
        run_id=latest.id if latest else 0,
        discovered=latest.leads_discovered if latest else 0,
        new=latest.leads_new if latest else 0,
        enriched=latest.leads_enriched if latest else 0,
        failed=latest.leads_failed if latest else 0,
        mock_mode=settings.effective_mock_mode,
    )


@router.get("/runs/latest")
def latest_run(db: Session = Depends(get_db)):
    run = repository.latest_run(db)
    if run is None:
        return {"status": "none"}
    return {
        "run_id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "leads_discovered": run.leads_discovered,
        "leads_new": run.leads_new,
        "leads_enriched": run.leads_enriched,
        "leads_failed": run.leads_failed,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
