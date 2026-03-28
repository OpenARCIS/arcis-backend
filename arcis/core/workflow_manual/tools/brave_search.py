import json
from typing import Optional

from langchain.tools import tool

from arcis.core.external_api.brave_search import brave_search_api
from arcis.logger import LOGGER


def _format_result(data: dict | list) -> str:
    """Compact JSON output for LLM consumption."""
    return json.dumps(data, indent=2, default=str)


@tool
async def brave_web_search(
    query: str,
    count: int = 5,
    country: Optional[str] = None,
    freshness: Optional[str] = None,
) -> str:
    """
    Search the web using Brave Search for current, up-to-date information.
    Use this whenever you need to find real-time information, verify facts,
    look up recent events, or research any topic on the internet.

    Args:
        query: The search query string (max 400 chars). Be specific for better results.
        count: Number of results to return (1-20, default 5).
        country: Optional 2-letter country code to bias results (e.g. 'US', 'IN', 'GB').
        freshness: Optional recency filter. Use 'pd' for past 24 hours, 'pw' for past week,
                   'pm' for past month, 'py' for past year. Or a date range 'YYYY-MM-DDtoYYYY-MM-DD'.
    """
    try:
        result = await brave_search_api.search(
            query=query,
            count=count,
            country=country,
            freshness=freshness,
        )
        if "error" in result:
            return f"Search failed: {result['error']}"

        # Build a clean, readable output for the LLM
        web_results = result.get("results", [])
        if not web_results:
            return f"No results found for '{query}'."

        output = f"Search results for '{query}' ({len(web_results)} results):\n"
        output += _format_result(web_results)

        # Append news if available
        news = result.get("news")
        if news:
            output += f"\n\nRelated news ({len(news)} articles):\n"
            output += _format_result(news)

        # Append FAQ if available
        faq = result.get("faq")
        if faq:
            output += f"\n\nRelated FAQs:\n"
            output += _format_result(faq)

        return output

    except ValueError as e:
        # Missing API key
        return f"Configuration error: {e}"
    except Exception as e:
        LOGGER.error(f"BRAVE_SEARCH_TOOL: {e}")
        return f"Search error: {e}"


# ===================================================================
# EXPORT: Tool list for easy registration
# ===================================================================

brave_search_tools = [
    brave_web_search,
]
