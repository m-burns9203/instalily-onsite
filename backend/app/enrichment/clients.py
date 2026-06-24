"""Thin wrappers around the OpenAI and Perplexity APIs.

Both expose an OpenAI-compatible chat-completions interface, so we use the
``openai`` SDK for both — Perplexity simply via a ``base_url`` override. Each
call is wrapped with bounded retries + exponential backoff (tenacity) to ride
out transient 429/5xx without hammering the provider.
"""
from __future__ import annotations

import logging

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

PERPLEXITY_BASE_URL = "https://api.perplexity.ai"


class AIClients:
    """Lazily-constructed provider clients. Safe to instantiate in mock mode."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._openai = None
        self._perplexity = None

    @property
    def openai(self):
        if self._openai is None:
            from openai import OpenAI

            self._openai = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.http_timeout_seconds,
            )
        return self._openai

    @property
    def perplexity(self):
        if self._perplexity is None:
            from openai import OpenAI

            self._perplexity = OpenAI(
                api_key=self.settings.perplexity_api_key,
                base_url=PERPLEXITY_BASE_URL,
                timeout=self.settings.http_timeout_seconds,
            )
        return self._perplexity

    # -- calls (retryable) -------------------------------------------------
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type(Exception),
    )
    def research(self, prompt: str) -> tuple[str, list[str]]:
        """Run web research via Perplexity. Returns (text, source_urls)."""
        resp = self.perplexity.chat.completions.create(
            model=self.settings.perplexity_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = resp.choices[0].message.content or ""
        # Perplexity returns citations alongside the completion.
        citations = getattr(resp, "citations", None) or []
        return text, list(citations)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type(Exception),
    )
    def structure(self, system: str, user: str) -> str:
        """Turn research into structured JSON via OpenAI (JSON mode)."""
        resp = self.openai.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"
