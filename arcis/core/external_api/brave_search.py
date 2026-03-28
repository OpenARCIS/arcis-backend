"""
Brave Search API — Async Wrapper for ARCIS.

Lightweight wrapper around the Brave Web Search API.  Returns simplified,
LLM-friendly dicts so a reasoning model can consume results as tool output.

Requires a Brave Search API key (free tier gives 2 000 queries/month).
Set the env var ``BRAVE_SEARCH_API_KEY``.

Docs: https://api.search.brave.com/app#/documentation/web-search
"""

from typing import Any, Dict, List, Optional

import httpx

from arcis import Config
from arcis.logger import LOGGER


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BRAVE_SEARCH_BASE = "https://api.search.brave.com/res/v1/web/search"


# ---------------------------------------------------------------------------
# Helpers — keep only the fields an LLM actually needs
# ---------------------------------------------------------------------------

def _simplify_web_result(r: dict) -> dict:
    """Distill a single Brave web result into a compact dict."""
    return {
        "title": r.get("title"),
        "url": r.get("url"),
        "description": r.get("description"),
        "age": r.get("age"),                       # e.g. "2 hours ago"
        "language": r.get("language"),
        "extra_snippets": r.get("extra_snippets"),  # list of additional text
    }


def _simplify_faq(faq: dict) -> dict:
    return {
        "question": faq.get("question"),
        "answer": faq.get("answer"),
        "url": faq.get("url"),
    }


def _simplify_news_result(n: dict) -> dict:
    return {
        "title": n.get("title"),
        "url": n.get("url"),
        "description": n.get("description"),
        "age": n.get("age"),
        "source": (n.get("meta_url") or {}).get("hostname"),
    }


# ---------------------------------------------------------------------------
# Main wrapper class
# ---------------------------------------------------------------------------

class BraveSearchAPI:
    """Async Brave Web Search API wrapper for LLM tool-use."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or Config.BRAVE_SEARCH_API_KEY
        if not self._api_key:
            raise ValueError(
                "Brave Search API key is required. "
                "Set BRAVE_SEARCH_API_KEY in your environment."
            )

    # -----------------------------------------------------------------------
    # Core HTTP helper
    # -----------------------------------------------------------------------

    async def _get(self, params: dict) -> Dict[str, Any]:
        """
        Make a GET request to the Brave Web Search endpoint.

        Returns the parsed JSON body, or a standardised error dict
        ``{"error": "...", "status_code": N}``.
        """
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                BRAVE_SEARCH_BASE,
                headers=headers,
                params=params,
                timeout=15.0,
            )

        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code >= 400:
            err_msg = data.get("message", resp.text[:300])
            LOGGER.error(
                f"BRAVE_SEARCH: {resp.status_code} — {err_msg}"
            )
            return {"error": err_msg, "status_code": resp.status_code}

        return data

    # ===================================================================
    # SEARCH
    # ===================================================================

    async def search(
        self,
        query: str,
        count: int = 10,
        country: Optional[str] = None,
        search_lang: Optional[str] = None,
        freshness: Optional[str] = None,
        offset: int = 0,
        safesearch: str = "moderate",
    ) -> Dict[str, Any]:
        """
        Search the web via Brave Search.

        Args:
            query:        Free-text search string (max 400 chars / 50 words).
            count:        Number of results to return (1-20, default 10).
            country:      2-letter country code (e.g. "US", "IN") to
                          bias results toward a specific region.
            search_lang:  Language code (e.g. "en", "hi") for results.
            freshness:    Recency filter. One of:
                          "pd"  — past 24 hours
                          "pw"  — past week
                          "pm"  — past month
                          "py"  — past year
                          Or a date range "YYYY-MM-DDtoYYYY-MM-DD".
            offset:       Pagination offset (0-9).
            safesearch:   "off", "moderate", or "strict".

        Returns:
            Dict with keys:
              - ``query``:    the query that was searched.
              - ``results``:  list of simplified web result dicts.
              - ``news``:     list of news results (if any).
              - ``faq``:      list of FAQ results (if any).
              - ``count``:    total number of web results returned.
        """
        params: Dict[str, Any] = {
            "q": query,
            "count": min(max(count, 1), 20),
            "offset": offset,
            "safesearch": safesearch,
        }
        if country:
            params["country"] = country
        if search_lang:
            params["search_lang"] = search_lang
        if freshness:
            params["freshness"] = freshness

        raw = await self._get(params)
        if "error" in raw:
            return raw

        # -- web results --------------------------------------------------
        web_section = raw.get("web", {})
        web_results = [
            _simplify_web_result(r)
            for r in web_section.get("results", [])
        ]

        # -- news results (if present) ------------------------------------
        news_section = raw.get("news", {})
        news_results = [
            _simplify_news_result(n)
            for n in news_section.get("results", [])
        ]

        # -- FAQ results (if present) -------------------------------------
        faq_section = raw.get("faq", {})
        faq_results = [
            _simplify_faq(f)
            for f in faq_section.get("results", [])
        ]

        return {
            "query": raw.get("query", {}).get("original", query),
            "count": len(web_results),
            "results": web_results,
            "news": news_results if news_results else None,
            "faq": faq_results if faq_results else None,
        }


# ---------------------------------------------------------------------------
# Lazy singleton — created on first use so missing key doesn't crash at import
# ---------------------------------------------------------------------------

_instance: Optional[BraveSearchAPI] = None


def _get_instance() -> BraveSearchAPI:
    global _instance
    if _instance is None:
        _instance = BraveSearchAPI()
    return _instance


class _LazyProxy:
    """Proxy that defers BraveSearchAPI construction until first attribute access."""

    def __getattr__(self, name):
        return getattr(_get_instance(), name)


brave_search_api = _LazyProxy()
