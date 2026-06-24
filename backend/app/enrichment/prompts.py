"""Prompt templates for the two-stage enrichment.

Stage 1 (Perplexity): live web research — gathers current, cited facts about
the contractor. Perplexity is used because it searches the web and returns
source URLs, which we surface to reps for trust.

Stage 2 (OpenAI): structuring — turns the research + scraped facts into a
strict JSON sales brief the UI renders directly.
"""
from __future__ import annotations

import json
from typing import Any

RESEARCH_PROMPT = """You are a B2B sales researcher for a roofing-materials \
distributor. Research the following roofing contractor and report concise, \
factual, up-to-date findings. Prefer recent and verifiable information.

Contractor: {name}
Location: {city}, {state} {zip_code}
Website: {website}
GAF certification: {certification}

Report on:
- Company size (employees / crews) and years in business, if known.
- Residential vs. commercial focus and roofing specialties (shingle, flat/TPO, \
metal, solar, etc.).
- Service areas / neighborhoods they cover.
- Any recent activity: expansion, hiring, new locations, awards, reviews, \
press, or storm-response work in the last 12-18 months.
- Likely material volume / scale of operations.

Be concise and specific. If something is unknown, say so rather than guessing."""


STRUCTURING_SYSTEM = """You are a sales-intelligence analyst for a roofing \
products distributor. You convert raw research about a roofing contractor into \
a structured sales brief that helps a distributor sales rep win the account. \
The contractor is a potential CUSTOMER who buys roofing materials. Respond with \
ONLY valid JSON matching the requested schema — no prose, no markdown."""


def build_structuring_prompt(lead: dict[str, Any], research: str) -> str:
    schema = {
        "summary": "2-3 sentence overview of the contractor as a sales prospect",
        "estimated_size": "e.g. 'Small (1-10)', 'Mid-size (11-50)', 'Large (50+)', or 'Unknown'",
        "years_in_business": "string e.g. '15+ years' or 'Unknown'",
        "specialties": ["list", "of", "roofing specialties"],
        "service_areas": ["list", "of", "areas served"],
        "recent_activity": "1-2 sentences on notable recent activity, or 'None found'",
        "recommended_products": [
            {
                "product": "product/category the distributor should pitch",
                "reason": "why it fits this contractor",
            }
        ],
        "talking_points": ["specific", "conversation openers for the rep"],
        "buying_signals": ["observable signals this account is worth pursuing now"],
        "outreach_strategy": "2-3 sentences: how and with whom to open the conversation",
        "decision_makers": [
            {
                "name": "person name or 'Unknown'",
                "title": "role",
                "rationale": "why this person matters",
                "linkedin_url": "url or null",
            }
        ],
        "lead_score": "integer 0-100 estimating account potential for the distributor",
    }
    return (
        f"Scraped facts about the contractor:\n{json.dumps(lead, indent=2)}\n\n"
        f"Web research findings:\n{research}\n\n"
        f"Produce a JSON object with exactly these keys:\n"
        f"{json.dumps(schema, indent=2)}"
    )
