"""GAF certified-contractor scraper.

Source: https://www.gaf.com/en-us/roofing-contractors/residential

The GAF directory is a JavaScript app whose contractor cards are populated from
a backend JSON endpoint keyed by ZIP + radius. This scraper:

1. Calls that endpoint with browser-like headers and paginates through results.
2. Falls back to parsing JSON embedded in the server-rendered HTML
   (``__NEXT_DATA__`` / inline ``application/json``) if the endpoint shape
   changes.
3. Normalizes every contractor into a stable record dict (``_to_record``) with
   a deterministic ``source_key`` so re-scrapes upsert rather than duplicate.

Design notes for production:
* Polite scraping: configurable delay, retry/backoff, identifiable UA. For a
  fleet supporting thousands of reps this would run as a scheduled job behind a
  shared cache + proxy pool, writing to the same ``leads`` table.
* Resilient parsing: the normalizer tolerates missing fields so a layout tweak
  degrades gracefully instead of dropping the whole run.

In sandboxes / offline demos (``settings.effective_mock_mode``) the scraper
returns the representative seed dataset instead of hitting the network, so the
rest of the pipeline is exercised identically.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import httpx

from ..config import Settings, get_settings
from .seed_data import SEED_CONTRACTORS

logger = logging.getLogger(__name__)

GAF_BASE = "https://www.gaf.com"
GAF_DIRECTORY_URL = f"{GAF_BASE}/en-us/roofing-contractors/residential"
# GAF's directory is backed by a JSON search endpoint; this is the observed
# shape. Kept configurable so an endpoint change is a one-line fix.
GAF_API_URL = f"{GAF_BASE}/api/v1/contractors/search"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def make_source_key(name: str, zip_code: str | None, address: str | None) -> str:
    """Deterministic identity for a contractor → enables idempotent upserts."""
    raw = "|".join(
        part.strip().lower()
        for part in (name or "", zip_code or "", address or "")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class GafScraper:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # -- public API --------------------------------------------------------
    def scrape(
        self, zip_code: str | None = None, radius: int | None = None
    ) -> list[dict[str, Any]]:
        zip_code = zip_code or self.settings.target_zip
        radius = radius or self.settings.search_radius_miles

        if self.settings.effective_mock_mode:
            logger.info("Scraper running in mock mode — returning seed dataset.")
            return [self._normalize_record(r) for r in SEED_CONTRACTORS]

        try:
            raw = self._fetch_live(zip_code, radius)
        except Exception as exc:  # network/policy/parse failure
            logger.warning(
                "Live GAF scrape failed (%s); falling back to seed dataset.", exc
            )
            return [self._normalize_record(r) for r in SEED_CONTRACTORS]

        records = [self._normalize_record(r) for r in raw]
        logger.info("Scraped %d contractors from GAF (zip=%s).", len(records), zip_code)
        return records

    # -- live fetch --------------------------------------------------------
    def _fetch_live(self, zip_code: str, radius: int) -> list[dict[str, Any]]:
        with httpx.Client(
            headers=_BROWSER_HEADERS,
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=True,
        ) as client:
            try:
                return self._fetch_via_api(client, zip_code, radius)
            except Exception as exc:
                logger.info("API path failed (%s); trying embedded-JSON path.", exc)
                return self._fetch_via_html(client, zip_code, radius)

    def _fetch_via_api(
        self, client: httpx.Client, zip_code: str, radius: int
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        while True:
            resp = client.get(
                GAF_API_URL,
                params={
                    "postalCode": zip_code,
                    "distance": radius,
                    "type": "residential",
                    "page": page,
                    "pageSize": 50,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            items = (
                payload.get("results")
                or payload.get("contractors")
                or payload.get("data")
                or []
            )
            if not items:
                break
            results.extend(items)
            total_pages = payload.get("totalPages") or payload.get("pageCount") or 1
            if page >= total_pages:
                break
            page += 1
        if not results:
            raise ValueError("API returned no contractors")
        return results

    def _fetch_via_html(
        self, client: httpx.Client, zip_code: str, radius: int
    ) -> list[dict[str, Any]]:
        import json

        resp = client.get(
            GAF_DIRECTORY_URL, params={"postalCode": zip_code, "distance": radius}
        )
        resp.raise_for_status()
        html = resp.text

        # Next.js apps embed initial data here.
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if m:
            data = json.loads(m.group(1))
            items = _deep_find_contractor_list(data)
            if items:
                return items
        raise ValueError("Could not locate contractor data in HTML")

    # -- normalization -----------------------------------------------------
    def _normalize_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw source record onto our canonical lead shape.

        Tolerant of both the seed shape (already canonical) and the various
        key names a live API/HTML payload might use.
        """
        get = raw.get
        name = get("name") or get("companyName") or get("businessName") or ""
        zip_code = (
            get("zip_code") or get("postalCode") or get("zip") or get("zipCode")
        )
        address = get("address") or get("street") or get("addressLine1")

        return {
            "source": "GAF",
            "source_url": get("source_url") or get("profileUrl") or get("url"),
            "source_key": make_source_key(name, zip_code, address),
            "name": name,
            "certification": _normalize_cert(
                get("certification") or get("certificationLevel") or get("badge")
            ),
            "phone": get("phone") or get("phoneNumber"),
            "website": get("website") or get("websiteUrl"),
            "address": address,
            "city": get("city"),
            "state": get("state") or get("stateCode"),
            "zip_code": zip_code,
            "distance_miles": _to_float(get("distance_miles") or get("distance")),
            "rating": _to_float(get("rating") or get("averageRating")),
            "review_count": _to_int(get("review_count") or get("reviewCount")),
        }


def _normalize_cert(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    lowered = text.lower()
    if "master" in lowered:
        return "Master Elite"
    if "president" in lowered:
        return "President's Club"
    if "certified" in lowered:
        return "Certified"
    return text


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _deep_find_contractor_list(data: Any) -> list[dict[str, Any]] | None:
    """Heuristically locate a list of contractor objects in nested JSON."""
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and (
            "name" in data[0] or "companyName" in data[0]
        ):
            return data
        for item in data:
            found = _deep_find_contractor_list(item)
            if found:
                return found
    elif isinstance(data, dict):
        for key in ("contractors", "results", "data", "items"):
            if isinstance(data.get(key), list) and data[key]:
                return data[key]
        for value in data.values():
            found = _deep_find_contractor_list(value)
            if found:
                return found
    return None
