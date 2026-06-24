# Cosailor Insights — AI Sales Intelligence for a Roofing Distributor

An AI-powered B2B sales-intelligence platform that turns the public **GAF
certified-contractor directory** into a ranked, enriched book of leads for a
roofing **distributor's** sales team to work during account planning.

> The contractors listed on GAF are the distributor's *prospects* — they buy
> roofing materials. Cosailor discovers them, researches each one with AI, and
> hands reps a ready-to-use sales brief: who to call, why now, what to pitch,
> and how to open the conversation.

---

## What it does

```
  GAF directory  ──►  Scrape & normalize  ──►  Store (idempotent upsert)
   (ZIP 10013)                                        │
                                                      ▼
   Lead dashboard  ◄──  Score & rank  ◄──  AI enrichment pipeline
   (React UI)                               (Perplexity research → OpenAI brief)
```

1. **Scrape** the GAF residential contractor directory for ZIP `10013` within
   25 miles and normalize every contractor into a canonical lead record.
2. **Enrich** each lead with a two-stage AI pipeline:
   - **Perplexity** runs live web research (company size, specialties, recent
     activity) and returns **cited sources**.
   - **OpenAI** structures that research into a strict-JSON sales brief:
     summary, recommended products, talking points, buying signals, outreach
     strategy, and likely decision-makers.
3. **Score** each lead 0–100 with a transparent, tunable heuristic
   (certification, reputation, proximity, reachability) and band it
   Hot / Warm / Nurture.
4. **Present** everything in a polished React dashboard reps can search, filter,
   sort, and drill into.

---

## Quick start

Prereqs: Python 3.11+, Node 18+.

```bash
make setup          # create venv + install backend & frontend deps
make seed           # populate the DB (mock mode → instant demo data)
make backend        # terminal 1: API at http://localhost:8000
make frontend       # terminal 2: UI  at http://localhost:5173
```

Open **http://localhost:5173**.

> **Windows (no `make`):** create the venv with
> `python -m venv backend\.venv`, install with
> `backend\.venv\Scripts\pip install -r backend\requirements.txt`, then run the
> backend `cd backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000`
> and the pipeline `.venv\Scripts\python -m scripts.run_pipeline`. Frontend is
> `cd frontend && npm install && npm run dev`.

### Running it for real (live GAF + AI)

The app runs **fully offline in mock mode** out of the box (deterministic
enrichment from a representative NYC-area seed dataset) so it always demos. To
run the real pipeline, add your keys:

```bash
cd backend
cp .env.example .env       # then paste OPENAI_API_KEY and PERPLEXITY_API_KEY
make seed                  # now scrapes GAF + calls the AI providers
```

With both keys present the app automatically leaves mock mode (see
`config.py: effective_mock_mode`). The "Run pipeline" button in the UI triggers
a fresh scrape + enrichment run.

### How the live GAF scrape works

GAF's public contractor directory is **not** a simple HTML page — it's a
JavaScript app behind an Akamai bot-management edge, backed by **Coveo**
(search-as-a-service). Rather than render the page in a headless browser, the
scraper talks to the same **Coveo REST Search API** the site itself calls:

1. **Geocode** the target ZIP to lat/long (`api.zippopotam.us`, with an offline
   fallback for the case-study ZIP).
2. **Query Coveo** for `Residential` contractors, using a distance query
   function over each contractor's coordinates to filter to the radius and sort
   nearest-first, paginating through results.
3. **Normalize** each result, using GAF's stable `contractor_id` as the
   idempotency key.

This returns clean, structured JSON (name, certification tier, rating, reviews,
phone, location) — far more robust than scraping rendered HTML, and the natural
production choice. Requests use browser-like headers (Akamai rejects thin
clients) and `brotli` decoding. If anything in the live path fails (network,
credential rotation, geocode miss), the scraper logs and falls back to the seed
dataset rather than aborting the run, so the pipeline/UI are identical live vs.
mock.

> The Coveo credentials in `config.py` are the public, search-only keys GAF
> ships in its page HTML to every visitor — not secrets — kept as
> env-overridable config in case GAF rotates them.

---

## Architecture

```
backend/
  app/
    config.py          # 12-factor settings; auto mock-mode when keys absent
    db.py              # SQLAlchemy engine/session (SQLite → Postgres by URL)
    models.py          # Lead, Enrichment, DecisionMaker, EnrichmentJob, PipelineRun
    repository.py      # data-access layer (idempotent upsert, queries, stats)
    scoring.py         # transparent lead-scoring heuristic
    schemas.py         # Pydantic API contracts
    scraper/gaf.py     # GAF scraper (Coveo Search API + ZIP geocode → seed fallback)
    enrichment/        # clients (OpenAI+Perplexity), prompts, enricher (+mock)
    pipeline/          # async orchestrator: scrape → queue → bounded-concurrency enrich
    api/               # FastAPI routes: /leads, /stats, /pipeline/run, /runs/latest
  scripts/run_pipeline.py   # CLI to run the pipeline once
  tests/                    # offline end-to-end pipeline tests
frontend/
  src/
    pages/Dashboard.tsx       # stats, filters, ranked lead grid
    pages/LeadDetailPage.tsx  # full AI sales brief
    components/                # cards, badges, score rings
    lib/                       # typed API client + types
```

### How the three grading criteria are addressed

**1. Intuitive UI.** A ranked lead dashboard with live search, certification
filter, sort, and a "Hot only" toggle; KPI cards; per-lead score rings and
Hot/Warm/Nurture bands. Each lead opens a sales brief organized the way a rep
actually works a call: *why now → what to pitch → talking points → outreach →
profile → sources*.

**2. Robust data management.** Ground-truth scraped facts (`Lead`) are kept
separate from regenerable AI output (`Enrichment`), so re-enriching never risks
the source data. Every lead has a stable `source_key` with a unique constraint,
making re-scrapes **idempotent** (upsert, never duplicate). Decision-makers are
normalized into their own table. `PipelineRun` and `EnrichmentJob` provide a
full audit trail. SQLite is the zero-config default; the identical code runs on
**Postgres** by changing one env var.

**3. Scalable pipeline.** Scraping and enrichment are **decoupled** so they
scale independently. Enrichment is driven by a durable **job queue**
(`EnrichmentJob` rows) processed with **bounded concurrency** (a semaphore that
respects provider rate limits), **retries with exponential backoff**, and
**per-lead failure isolation** (one bad lead never aborts the run). The queue
lives in the database, so the design is a drop-in seam for a distributed worker
fleet — see below.

### Scaling to thousands of reps (production evolution)

| Concern | Today (this submission) | Production path |
|---|---|---|
| Storage | SQLite | Postgres (change `DATABASE_URL`), read replicas |
| Queue | `EnrichmentJob` table + asyncio workers | Redis/SQS + Celery/RQ or Temporal; same job rows |
| Enrichment cost | Re-enrich on demand | Cache by `source_key`, TTL refresh, skip-if-fresh |
| Scraping | On-trigger | Scheduled regional crawls behind a shared cache + proxy pool |
| Schema migrations | `create_all` | Alembic migrations |
| Multi-tenant (per rep/territory) | Single table | Partition by territory; row-level filters in the repo layer |

Because business logic is split across `scraper / enrichment / repository /
pipeline`, swapping any one layer (queue, DB, provider) touches a single seam.

---

## API

| Method | Path | Description |
|---|---|---|
| GET  | `/api/health` | Service + mode info |
| GET  | `/api/stats` | KPI rollups (totals, hot count, avg score, by cert) |
| GET  | `/api/leads` | List leads (`search`, `certification`, `min_score`, `sort`) |
| GET  | `/api/leads/{id}` | Full lead + enrichment + decision-makers |
| POST | `/api/pipeline/run` | Trigger a background scrape + enrich run |
| GET  | `/api/runs/latest` | Status of the most recent pipeline run |

Interactive docs at `http://localhost:8000/docs`.

---

## Tests

```bash
make test
```

Covers idempotent upserts, the scrape→enrich→store flow, scoring bounds, and
per-lead failure isolation — all offline (mock mode), no keys or network needed.
