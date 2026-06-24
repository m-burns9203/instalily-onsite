"""Outreach draft generation.

Turns a lead + its AI enrichment into a *ready-to-send* artifact for the rep -
a personalized cold email and a cold-call opener. This is the actionable payoff
of the enrichment: the brief tells the rep *why* a lead matters; the draft gives
them something to actually send.

It is composed deterministically from data already in the database (scraped
facts + the stored `Enrichment`), so it is instant, free (no extra AI call), and
demos identically online or offline. The same seams would let a production build
swap in a per-request LLM call for more bespoke copy.
"""
from __future__ import annotations

from typing import Any

from .models import Lead


def _first(items: list[Any] | None) -> Any | None:
    return items[0] if items else None


def build_outreach(lead: Lead, enrichment, decision_makers: list) -> dict[str, Any]:
    """Compose an email + call opener for one lead. Pure function of stored data."""
    name = lead.name or "your team"
    city = lead.city or "your area"
    rating = lead.rating
    reviews = lead.review_count
    cert = lead.certification

    # Most senior decision-maker we know of (names are often "Unknown"; the title
    # is what the rep actually opens with).
    contact = None
    for dm in decision_makers:
        title = (dm.title or "").lower()
        if "owner" in title or "president" in title:
            contact = dm
            break
    contact = contact or _first(decision_makers)
    greeting_name = (
        contact.name
        if contact and contact.name and contact.name != "Unknown"
        else "there"
    )
    # Keep the role readable ("CEO", "Owner") and take the first segment if the
    # title is compound like "Owner / President".
    contact_role = (contact.title if contact and contact.title else "owner")
    contact_role = contact_role.split("/")[0].strip() or "owner"

    # Pull the strongest hooks from the enrichment.
    top_product = None
    products = _loads_products(enrichment)
    if products:
        p = products[0]
        top_product = p.get("product") if isinstance(p, dict) else None
    top_signal = _first(_loads_list(enrichment, "buying_signals"))
    talking_points = _loads_list(enrichment, "talking_points")

    # --- Reputation hook -------------------------------------------------
    if rating and reviews:
        rep_hook = (
            f"Congrats on maintaining a {rating}-star rating across "
            f"{reviews} reviews - that kind of steady demand says you're "
            f"moving real volume."
        )
    elif cert:
        rep_hook = (
            f"Your GAF {cert} status stood out to us - it tells us you're "
            f"committed to premium roofing systems."
        )
    else:
        rep_hook = (
            f"You came up as one of the established roofing contractors working "
            f"around {city}."
        )

    # --- Value line ------------------------------------------------------
    product_line = (
        f"We can keep {top_product} in stock for you with next-day delivery to "
        f"{city} job sites, at contractor-tier pricing."
        if top_product
        else f"We can keep your core GAF systems in stock with next-day delivery "
        f"to {city} job sites, at contractor-tier pricing."
    )

    subject = (
        f"GAF supply + contractor pricing for {name}"
        if len(name) < 40
        else "GAF supply + contractor pricing for your crews"
    )

    greeting = f"Hi {greeting_name},"
    email_body = "\n\n".join(
        [
            greeting,
            f"I'm reaching out from your local GAF roofing-materials distributor. "
            f"{rep_hook}",
            product_line,
            (
                "Would you be open to a quick call to set up a contractor account "
                "and lock in pricing on your next few jobs? I can also include a "
                "co-branded marketing rebate to help you win more bids."
            ),
            "Best,\n[Your name]\n[Distributor] - [phone]",
        ]
    )

    # --- Cold-call opener ------------------------------------------------
    call_opener = (
        f"Hi, this is [name] with your local GAF distributor - is the "
        f"{contact_role} in? "
    )
    if top_signal:
        sig = top_signal.rstrip(". ").strip()
        sig = sig[0].lower() + sig[1:] if sig else sig
        call_opener += (
            f"I noticed {sig}, so I wanted to reach out about getting you set up "
            f"with contractor pricing and reliable local supply."
        )
    else:
        call_opener += (
            "I wanted to reach out about getting you set up with contractor "
            "pricing and reliable local supply for your GAF systems."
        )

    return {
        "subject": subject,
        "email_body": email_body,
        "call_opener": call_opener,
        "talking_points": talking_points,
        "contact": {
            "name": greeting_name if greeting_name != "there" else None,
            "title": contact.title if contact else None,
        },
    }


# -- helpers: read JSON-encoded enrichment fields without circular imports ---
def _loads_list(enrichment, field: str) -> list:
    import json

    if enrichment is None:
        return []
    raw = getattr(enrichment, field, None)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _loads_products(enrichment) -> list:
    return _loads_list(enrichment, "recommended_products")
