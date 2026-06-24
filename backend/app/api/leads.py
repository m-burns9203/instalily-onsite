"""Lead + stats read endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import repository
from ..db import get_db
from ..schemas import LeadDetail, LeadListOut, LeadSummary, StatsOut

router = APIRouter(prefix="/api", tags=["leads"])


@router.get("/leads", response_model=LeadListOut)
def get_leads(
    search: str | None = None,
    status: str | None = None,
    certification: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    sort: str = Query(default="score", pattern="^(score|name|distance|rating)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    leads, total = repository.list_leads(
        db,
        search=search,
        status=status,
        certification=certification,
        min_score=min_score,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return LeadListOut(
        total=total, items=[LeadSummary.from_model(l) for l in leads]
    )


@router.get("/leads/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = repository.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadDetail.from_model(lead)


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    return StatsOut(**repository.stats(db))
