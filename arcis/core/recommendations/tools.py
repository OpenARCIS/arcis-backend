"""
Tools available to the Recommendation ReAct agent.

Each tool is a read-only data-fetching function that the agent can call
during its research phase.  Adding a new data source is as simple as:
  1. Write a new @tool async function below (or import from another module).
  2. Append it to the `recommendation_tools` list at the bottom.

Current data sources:
  - Calendar          — upcoming events / todos
  - Emotion history   — recent mood data
  - Long-term memory  — user preferences / facts
  - Web search        — external context (weather, news, tips)
  - Spotify           — listening history, top items, music discovery
  - TMDB              — trending / popular / top-rated movies & TV shows

Note: Only READ-ONLY / DISCOVERY tools are included here.  Playback
control, playlist mutations, and follow actions are excluded because the
recommendation engine runs headlessly and should never take actions on
behalf of the user.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from langchain.tools import tool

from arcis.core.external_api.internal_calendar import calendar_wrapper
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.logger import LOGGER


# ===================================================================
# CALENDAR
# ===================================================================

@tool
async def get_upcoming_calendar(hours_ahead: int = 24) -> str:
    """
    Fetch upcoming calendar events, todos, and reminders.

    Args:
        hours_ahead: How many hours into the future to look (default 24).
    """
    try:
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)
        items = await calendar_wrapper.get_items_in_range(now, end)

        if not items:
            return json.dumps({
                "status": "no_events",
                "hours_ahead": hours_ahead,
                "message": "No upcoming events found in this time range."
            }, indent=2)

        # Simplify for LLM consumption
        simplified = []
        for item in items[:15]:  # cap to avoid token blow-up
            simplified.append({
                "title": item.get("title", "Untitled"),
                "type": item.get("item_type", "event"),
                "start_time": str(item.get("start_time", "")),
                "end_time": str(item.get("end_time", "")) if item.get("end_time") else None,
                "description": (item.get("description", "") or "")[:200],
                "is_completed": item.get("is_completed", False),
            })

        return json.dumps({
            "status": "success",
            "count": len(simplified),
            "hours_ahead": hours_ahead,
            "events": simplified,
        }, indent=2, default=str)

    except Exception as e:
        LOGGER.warning(f"RECOMMENDATION TOOL: Calendar fetch failed: {e}")
        return json.dumps({"status": "error", "message": str(e)})


# ===================================================================
# EMOTION / MOOD HISTORY
# ===================================================================

@tool
async def get_emotion_history(limit: int = 5) -> str:
    """
    Fetch recent emotion/mood records for the user, newest first.
    Each record contains emotion scores (happiness, frustration, urgency,
    confusion) and the user's input text that triggered the analysis.

    Args:
        limit: Number of recent records to fetch (default 5).
    """
    try:
        cursor = (
            mongo.db[COLLECTIONS["user_emotions"]]
            .find()
            .sort("timestamp", -1)
            .limit(limit)
        )
        records = []
        async for doc in cursor:
            records.append({
                "emotions": doc.get("emotions", {}),
                "input_text": (doc.get("input_text", "") or "")[:300],
                "timestamp": str(doc.get("timestamp", "")),
            })

        if not records:
            return json.dumps({
                "status": "no_data",
                "message": "No emotion data recorded yet."
            }, indent=2)

        return json.dumps({
            "status": "success",
            "count": len(records),
            "records": records,
        }, indent=2, default=str)

    except Exception as e:
        LOGGER.warning(f"RECOMMENDATION TOOL: Emotion fetch failed: {e}")
        return json.dumps({"status": "error", "message": str(e)})


# ===================================================================
# LONG-TERM MEMORY SEARCH (re-uses the existing memory system)
# ===================================================================

# We import the existing tool directly so the agent can use it as-is.
from arcis.core.workflow_manual.tools.memory_search import memory_search


# ===================================================================
# WEB SEARCH (re-uses the existing brave search tool)
# ===================================================================

from arcis.core.workflow_manual.tools.brave_search import brave_web_search


# ===================================================================
# SPOTIFY — listening history & music discovery (read-only)
# ===================================================================

from arcis.core.workflow_manual.tools.spotify import (
    spotify_get_currently_playing,
    spotify_get_recently_played,
    spotify_get_top_items,
    spotify_get_recommendations,
    spotify_get_genre_seeds,
    spotify_get_new_releases,
    spotify_get_featured_playlists,
)


# ===================================================================
# TMDB — movies & TV trending / discovery (read-only)
# ===================================================================

from arcis.core.workflow_manual.tools.tmdb import (
    tmdb_get_trending,
    tmdb_get_popular,
    tmdb_get_top_rated,
    tmdb_get_now_playing,
    tmdb_get_upcoming_movies,
    tmdb_get_airing_today,
    tmdb_discover_movies,
    tmdb_discover_tv,
    tmdb_search,
    tmdb_get_genres,
)


# ===================================================================
# TOOL REGISTRY
# ===================================================================

recommendation_tools = [
    # Core context
    get_upcoming_calendar,
    get_emotion_history,
    memory_search,
    brave_web_search,
    # Spotify — music listening context & discovery
    spotify_get_currently_playing,
    spotify_get_recently_played,
    spotify_get_top_items,
    spotify_get_recommendations,
    spotify_get_genre_seeds,
    spotify_get_new_releases,
    spotify_get_featured_playlists,
    # TMDB — movies & TV discovery
    tmdb_get_trending,
    tmdb_get_popular,
    tmdb_get_top_rated,
    tmdb_get_now_playing,
    tmdb_get_upcoming_movies,
    tmdb_get_airing_today,
    tmdb_discover_movies,
    tmdb_discover_tv,
    tmdb_search,
    tmdb_get_genres,
]
