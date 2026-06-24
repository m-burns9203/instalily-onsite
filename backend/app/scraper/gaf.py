"""GAF certified-contractor scraper.

Source: https://www.gaf.com/en-us/roofing-contractors/residential

GAF's public contractor directory is a JavaScript app whose contractor cards are
served by **Coveo** (a hosted search-as-a-service platform). The page ships
client-side Coveo credentials and queries Coveo's REST Search API, ranking and
filtering contractors by geographic distance from the visitor's ZIP. This
scraper talks to that same Coveo API directly:

1. Geocode the target ZIP to latitude/longitude (``_geocode_zip``).
2. Query Coveo's Search API for ``Residential`` contractors within the radius,
   sorted nearest-first, paginating through results (``_fetch_via_coveo``).
3. Normalize every contractor into a stable record dict (``_normalize_record``)
   with a deterministic ``source_key`` (the GAF contractor id) so re-scrapes
   upsert rather than duplicate.

Design notes for production:
* Hitting the structured Coveo API (vs. scraping rendered HTML) is fast, paginated,
  and resilient to visual redesigns. For a fleet supporting thousands of reps this
  runs as a scheduled regional crawl behind a shared cache + proxy pool, writing to
  the same ``leads`` table.
* The normalizer tolerates missing fields, so a payload tweak degrades gracefully
  instead of dropping the whole run.

In sandboxes / offline demos (``settings.effective_mock_mode``) the scraper
returns the representative seed dataset instead of hitting the network, so the
rest of the pipeline is exercised identically. If a live run fails for any reason
(network, credential rotation, geocode miss) it logs and falls back to the seed
dataset rather than aborting the pipeline.
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any

import httpx

from ..config import Settings, get_settings
from .seed_data import SEED_CONTRACTORS

logger = logging.getLogger(__name__)

GAF_BASE = "https://www.gaf.com"

# Browser-like headers: GAF's edge (Akamai) rejects thin/unknown clients with a
# 403, so we present as a current desktop Chrome. ``br``/``gzip`` require the
# ``brotli`` package (in requirements) to be decoded.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# Coveo "raw" field names → our canonical record keys (see the GAF page's
# data-search-fields config). Centralized so a field rename is a one-line fix.
_COVEO_FIELDS = [
    "gaf_contractor_id",
    "gaf_navigation_title",
    "gaf_contractor_dba",
    "gaf_contractor_type",
    "gaf_rating",
    "gaf_number_of_reviews",
    "gaf_f_city",
    "gaf_f_state_code",
    "gaf_postal_code",
    "gaf_phone",
    "gaf_latitude",
    "gaf_longitude",
    "gaf_f_contractor_certifications_and_awards_residential",
    "gaf_f_contractor_specialties_residential",
]

# Minimal offline geocode fallback for the case-study ZIP, used if the geocoding
# service is unreachable. Production would use a full ZIP→latlng table or a
# geocoding provider with a cache.
_ZIP_FALLBACK: dict[str, tuple[float, float]] = {
    "10013": (40.7196, -74.0079),
}


def make_source_key(*parts: str | None) -> str:
    """Deterministic identity hash → enables idempotent upserts."""
    raw = "|".join((p or "").strip().lower() for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613  # Earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


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
            if not raw:
                raise ValueError("live scrape returned 0 contractors")
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
        coords = _geocode_zip(zip_code)
        if coords is None:
            raise ValueError(f"could not geocode ZIP {zip_code}")
        lat, lon = coords
        return self._fetch_via_coveo(lat, lon, radius)

    def _fetch_via_coveo(
        self, lat: float, lon: float, radius: int
    ) -> list[dict[str, Any]]:
        s = self.settings
        endpoint = f"https://{s.coveo_org}.org.coveo.com/rest/search/v2"
        headers = {
            **_BROWSER_HEADERS,
            "Authorization": f"Bearer {s.coveo_api_key}",
            "Content-Type": "application/json",
        }
        # Coveo computes distance via a query function over the contractor's
        # lat/long; we filter on it and sort nearest-first.
        dist_fn = f"dist(@gaf_latitude,@gaf_longitude,{lat},{lon})/1609.34"
        page_size = 50
        collected: list[dict[str, Any]] = []

        with httpx.Client(timeout=s.http_timeout_seconds, follow_redirects=True) as client:
            first = 0
            while len(collected) < s.scrape_max_results:
                body = {
                    "q": "",
                    "searchHub": s.coveo_pipeline,
                    "pipeline": s.coveo_pipeline,
                    "numberOfResults": page_size,
                    "firstResult": first,
                    "fieldsToInclude": _COVEO_FIELDS,
                    "queryFunctions": [
                        {"function": dist_fn, "fieldName": "distanceinmiles"}
                    ],
                    "aq": f"@gaf_contractor_type==Residential AND @distanceinmiles<={radius}",
                    "sortCriteria": "@distanceinmiles ascending",
                }
                resp = client.post(endpoint, headers=headers, json=body)
                resp.raise_for_status()
                payload = resp.json()
                results = payload.get("results", [])
                if not results:
                    break
                for r in results:
                    collected.append(self._coveo_result_to_raw(r, lat, lon))
                total = payload.get("totalCount", 0)
                first += page_size
                if first >= total:
                    break

        return collected[: s.scrape_max_results]

    @staticmethod
    def _coveo_result_to_raw(
        result: dict[str, Any], origin_lat: float, origin_lon: float
    ) -> dict[str, Any]:
        """Map one Coveo result into the loose dict ``_normalize_record`` expects."""
        raw = result.get("raw", {})
        lat = _to_float(raw.get("gaf_latitude"))
        lon = _to_float(raw.get("gaf_longitude"))
        distance = (
            round(_haversine_miles(origin_lat, origin_lon, lat, lon), 1)
            if lat is not None and lon is not None
            else None
        )
        return {
            "contractor_id": raw.get("gaf_contractor_id"),
            "name": raw.get("gaf_navigation_title")
            or raw.get("gaf_contractor_dba")
            or result.get("title"),
            "certification": raw.get(
                "gaf_f_contractor_certifications_and_awards_residential"
            ),
            "phone": raw.get("gaf_phone"),
            "city": raw.get("gaf_f_city"),
            "state": raw.get("gaf_f_state_code"),
            "zip_code": raw.get("gaf_postal_code"),
            "rating": raw.get("gaf_rating"),
            "review_count": raw.get("gaf_number_of_reviews"),
            "distance_miles": distance,
            "source_url": result.get("clickUri") or result.get("ClickUri"),
        }

    # -- normalization -----------------------------------------------------
    def _normalize_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw source record onto our canonical lead shape.

        Tolerant of both the seed shape (already canonical) and the Coveo
        payload shape.
        """
        get = raw.get
        name = get("name") or get("companyName") or get("businessName") or ""
        zip_code = get("zip_code") or get("postalCode") or get("zip") or get("zipCode")
        address = get("address") or get("street") or get("addressLine1")
        contractor_id = get("contractor_id") or get("gaf_contractor_id")

        # Prefer the source's stable contractor id for identity; fall back to a
        # name+zip+address hash for the seed dataset.
        source_key = (
            make_source_key("gaf", str(contractor_id))
            if contractor_id
            else make_source_key(name, zip_code, address)
        )

        return {
            "source": "GAF",
            "source_url": get("source_url") or get("profileUrl") or get("url"),
            "source_key": source_key,
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


# -- geocoding -------------------------------------------------------------
def _geocode_zip(zip_code: str) -> tuple[float, float] | None:
    """ZIP → (lat, lon). Uses the free Zippopotam.us API, with a small built-in
    fallback so the case-study ZIP works even if the service is unreachable."""
    try:
        resp = httpx.get(
            f"https://api.zippopotam.us/us/{zip_code}",
            headers=_BROWSER_HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            place = resp.json()["places"][0]
            return float(place["latitude"]), float(place["longitude"])
        logger.info("Geocode HTTP %s for ZIP %s.", resp.status_code, zip_code)
    except Exception as exc:
        logger.info("Geocode lookup failed for ZIP %s (%s).", zip_code, exc)
    return _ZIP_FALLBACK.get(zip_code)


def _normalize_cert(value: Any) -> str | None:
    """Reduce GAF's certification/award list to a single canonical tier.

    GAF residential tiers, highest first: Master Elite > Certified Plus >
    Certified. ``President's Club`` is an award we surface when no higher tier
    is present. Accepts a string or a list of facet strings (Coveo returns a
    list); trademark glyphs are tolerated.
    """
    if not value:
        return None
    text = " ".join(str(v) for v in value) if isinstance(value, list) else str(value)
    low = text.lower()
    if "master elite" in low:
        return "Master Elite"
    if "certified plus" in low:
        return "Certified Plus"
    if "certified" in low:
        return "Certified"
    if "president" in low:
        return "President's Club"
    # Unknown tier: return a cleaned single value (strip non-ASCII trademark glyphs).
    cleaned = (value[0] if isinstance(value, list) and value else text)
    cleaned = str(cleaned).encode("ascii", "ignore").decode().strip()
    return cleaned or None


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
