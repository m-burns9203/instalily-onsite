"""FastAPI application entrypoint.

Run: uvicorn app.main:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import leads, pipeline
from .config import get_settings
from .db import init_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(
    title="Cosailor Insights",
    description="AI-powered B2B sales intelligence for roofing distributors.",
    version="1.0.0",
)

# The React dev server runs on a different origin; allow it in dev. Lock this
# down to known origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(pipeline.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "mock_mode": settings.effective_mock_mode,
        "target_zip": settings.target_zip,
        "radius_miles": settings.search_radius_miles,
    }
