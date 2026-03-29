import json
from typing import Optional

from langchain.tools import tool

from arcis.core.external_api.tmdb import tmdb_api
from arcis.logger import LOGGER


def _fmt(data: dict | list) -> str:
    """Compact JSON output for LLM consumption."""
    return json.dumps(data, indent=2, default=str)


# ===================================================================
# SEARCH
# ===================================================================

@tool
async def tmdb_search(
    query: str,
    media_type: str = "multi",
    page: int = 1,
    year: Optional[int] = None,
) -> str:
    """
    Search TMDB for movies, TV shows, and people.
    This is the primary entry point when the user mentions a movie, show,
    actor, or director by name.

    Args:
        query: Free-text search query (e.g. 'Inception', 'Breaking Bad', 'Leonardo DiCaprio').
        media_type: What to search for — 'multi' (default, returns all types),
                    'movie', 'tv', or 'person'.
        page: Page number for pagination (default 1, 20 results per page).
        year: Optional year filter. For movies: release year. For TV: first air date year.
    """
    try:
        if media_type == "movie":
            result = await tmdb_api.search_movies(query, page=page, year=year)
        elif media_type == "tv":
            result = await tmdb_api.search_tv(
                query, page=page, first_air_date_year=year,
            )
        elif media_type == "person":
            result = await tmdb_api.search_person(query, page=page)
        else:
            result = await tmdb_api.search_multi(query, page=page)

        if "error" in result:
            return f"❌ Search failed: {result['error']}"

        total = result.get("total_results", 0)
        if total == 0:
            return f"No results found for '{query}'."

        return f"🔍 TMDB search results for '{query}' ({total} total, page {result.get('page')}/{result.get('total_pages')}):\n{_fmt(result)}"
    except ValueError as e:
        return f"❌ Configuration error: {e}"
    except Exception as e:
        LOGGER.error(f"TMDB_TOOL: Search error — {e}")
        return f"❌ Search error: {e}"


# ===================================================================
# MOVIE DETAILS
# ===================================================================

@tool
async def tmdb_get_movie(movie_id: int) -> str:
    """
    Get detailed information about a specific movie by its TMDB ID.
    Returns: title, tagline, overview, runtime, genres, ratings, budget,
    revenue, production companies, and poster/backdrop URLs.

    Args:
        movie_id: The TMDB movie ID (e.g. 550 for Fight Club).
    """
    try:
        result = await tmdb_api.get_movie(movie_id)
        if "error" in result:
            return f"❌ Failed to get movie: {result['error']}"
        return f"🎬 Movie details:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_movie_credits(movie_id: int) -> str:
    """
    Get the cast and key crew (director, writer, producer) for a movie.

    Args:
        movie_id: The TMDB movie ID.
    """
    try:
        result = await tmdb_api.get_movie_credits(movie_id)
        if "error" in result:
            return f"❌ Failed to get credits: {result['error']}"
        return f"🎭 Cast & Crew for movie {movie_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_movie_recommendations(movie_id: int, page: int = 1) -> str:
    """
    Get movies recommended by TMDB based on a specific movie.
    Useful when the user says 'movies like X' or wants similar content.

    Args:
        movie_id: The TMDB movie ID to base recommendations on.
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_movie_recommendations(movie_id, page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎬 Recommendations based on movie {movie_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_movie_reviews(movie_id: int, page: int = 1) -> str:
    """
    Get user reviews for a movie. Useful to understand audience reception.

    Args:
        movie_id: The TMDB movie ID.
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_movie_reviews(movie_id, page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📝 Reviews for movie {movie_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_movie_videos(movie_id: int) -> str:
    """
    Get trailers, teasers, and clips for a movie.
    Returns YouTube URLs when available.

    Args:
        movie_id: The TMDB movie ID.
    """
    try:
        result = await tmdb_api.get_movie_videos(movie_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎥 Videos for movie {movie_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_movie_watch_providers(movie_id: int) -> str:
    """
    Find out where to watch a movie — which streaming services, rent, or buy.
    Shows availability for major regions (US, GB, IN, CA, AU, DE, FR).

    Args:
        movie_id: The TMDB movie ID.
    """
    try:
        result = await tmdb_api.get_movie_watch_providers(movie_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📺 Watch providers for movie {movie_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# TV SHOW DETAILS
# ===================================================================

@tool
async def tmdb_get_tv_show(tv_id: int) -> str:
    """
    Get detailed information about a specific TV show by its TMDB ID.
    Returns: name, overview, seasons, creators, networks, genres, ratings, etc.

    Args:
        tv_id: The TMDB TV show ID (e.g. 1396 for Breaking Bad).
    """
    try:
        result = await tmdb_api.get_tv_show(tv_id)
        if "error" in result:
            return f"❌ Failed to get TV show: {result['error']}"
        return f"📺 TV show details:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_tv_credits(tv_id: int) -> str:
    """
    Get the cast and key crew for a TV show.

    Args:
        tv_id: The TMDB TV show ID.
    """
    try:
        result = await tmdb_api.get_tv_credits(tv_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎭 Cast & Crew for TV show {tv_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_tv_recommendations(tv_id: int, page: int = 1) -> str:
    """
    Get TV shows recommended based on a specific show.
    Useful when the user says 'shows like X' or wants similar content.

    Args:
        tv_id: The TMDB TV show ID to base recommendations on.
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_tv_recommendations(tv_id, page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📺 Recommendations based on TV show {tv_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_tv_reviews(tv_id: int, page: int = 1) -> str:
    """
    Get user reviews for a TV show.

    Args:
        tv_id: The TMDB TV show ID.
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_tv_reviews(tv_id, page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📝 Reviews for TV show {tv_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_tv_videos(tv_id: int) -> str:
    """
    Get trailers, teasers, and clips for a TV show.

    Args:
        tv_id: The TMDB TV show ID.
    """
    try:
        result = await tmdb_api.get_tv_videos(tv_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎥 Videos for TV show {tv_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_tv_watch_providers(tv_id: int) -> str:
    """
    Find out where to watch a TV show — streaming, rent, or buy.
    Shows availability for major regions.

    Args:
        tv_id: The TMDB TV show ID.
    """
    try:
        result = await tmdb_api.get_tv_watch_providers(tv_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📺 Watch providers for TV show {tv_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_tv_season(tv_id: int, season_number: int) -> str:
    """
    Get details for a specific season of a TV show, including all episodes
    with names, air dates, overviews, and ratings.

    Args:
        tv_id: The TMDB TV show ID.
        season_number: Season number (0 for specials, 1+ for regular seasons).
    """
    try:
        result = await tmdb_api.get_tv_season(tv_id, season_number)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📺 Season {season_number} details:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# PERSON DETAILS
# ===================================================================

@tool
async def tmdb_get_person(person_id: int) -> str:
    """
    Get detailed info about an actor, director, or other crew member.
    Returns: biography, birthday, filmography highlights, etc.

    Args:
        person_id: The TMDB person ID.
    """
    try:
        result = await tmdb_api.get_person(person_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"👤 Person details:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_person_movie_credits(person_id: int) -> str:
    """
    Get a person's movie credits — what movies they appeared in or worked on.
    Sorted by popularity, limited to top 20 acting + top 10 crew roles.

    Args:
        person_id: The TMDB person ID.
    """
    try:
        result = await tmdb_api.get_person_movie_credits(person_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎬 Movie credits for person {person_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_person_tv_credits(person_id: int) -> str:
    """
    Get a person's TV credits — what shows they appeared in or worked on.
    Sorted by popularity, limited to top 20 acting + top 10 crew roles.

    Args:
        person_id: The TMDB person ID.
    """
    try:
        result = await tmdb_api.get_person_tv_credits(person_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📺 TV credits for person {person_id}:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# TRENDING
# ===================================================================

@tool
async def tmdb_get_trending(
    media_type: str = "all",
    time_window: str = "day",
    page: int = 1,
) -> str:
    """
    Get what's trending on TMDB right now — movies, TV shows, or people.
    Great for 'what's popular', 'what should I watch', or current buzz.

    Args:
        media_type: 'all' (default), 'movie', 'tv', or 'person'.
        time_window: 'day' (default, past 24h) or 'week' (past 7 days).
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_trending(
            media_type=media_type, time_window=time_window, page=page,
        )
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🔥 Trending {media_type} ({time_window}):\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# DISCOVER — Advanced filtered browsing
# ===================================================================

@tool
async def tmdb_discover_movies(
    sort_by: str = "popularity.desc",
    with_genres: Optional[str] = None,
    release_year: Optional[int] = None,
    vote_average_gte: Optional[float] = None,
    vote_count_gte: Optional[int] = None,
    language_filter: Optional[str] = None,
    page: int = 1,
) -> str:
    """
    Discover movies using advanced filters. Use this when the user wants to
    browse by genre, year, rating, or language rather than searching by name.
    Use tmdb_get_genres first to look up the correct genre IDs.

    Args:
        sort_by: How to sort results. Options: 'popularity.desc' (default),
                 'popularity.asc', 'vote_average.desc', 'vote_average.asc',
                 'primary_release_date.desc', 'primary_release_date.asc',
                 'revenue.desc', 'revenue.asc'.
        with_genres: Comma-separated genre IDs to include (e.g. '28,12' for Action+Adventure).
        release_year: Filter to a specific release year (e.g. 2024).
        vote_average_gte: Minimum rating out of 10 (e.g. 7.0 for well-reviewed movies).
        vote_count_gte: Minimum number of votes (use ≥100 to filter out obscure titles).
        language_filter: Original language code (e.g. 'en', 'ko', 'ja', 'hi').
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.discover_movies(
            page=page,
            sort_by=sort_by,
            with_genres=with_genres,
            primary_release_year=release_year,
            vote_average_gte=vote_average_gte,
            vote_count_gte=vote_count_gte,
            with_original_language=language_filter,
        )
        if "error" in result:
            return f"❌ Discover failed: {result['error']}"
        return f"🎬 Discover movies (page {result.get('page')}/{result.get('total_pages')}, {result.get('total_results')} total):\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_discover_tv(
    sort_by: str = "popularity.desc",
    with_genres: Optional[str] = None,
    first_air_date_year: Optional[int] = None,
    vote_average_gte: Optional[float] = None,
    vote_count_gte: Optional[int] = None,
    language_filter: Optional[str] = None,
    page: int = 1,
) -> str:
    """
    Discover TV shows using advanced filters. Like tmdb_discover_movies but
    for TV. Use tmdb_get_genres to look up TV genre IDs.

    Args:
        sort_by: Sort order (same options as movies).
        with_genres: Comma-separated TV genre IDs.
        first_air_date_year: Filter to shows that first aired in this year.
        vote_average_gte: Minimum rating out of 10.
        vote_count_gte: Minimum number of votes.
        language_filter: Original language code.
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.discover_tv(
            page=page,
            sort_by=sort_by,
            with_genres=with_genres,
            first_air_date_year=first_air_date_year,
            vote_average_gte=vote_average_gte,
            vote_count_gte=vote_count_gte,
            with_original_language=language_filter,
        )
        if "error" in result:
            return f"❌ Discover failed: {result['error']}"
        return f"📺 Discover TV (page {result.get('page')}/{result.get('total_pages')}, {result.get('total_results')} total):\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# CURATED LISTS (Popular, Top Rated, Now Playing, etc.)
# ===================================================================

@tool
async def tmdb_get_popular(media_type: str = "movie", page: int = 1) -> str:
    """
    Get currently popular movies or TV shows.

    Args:
        media_type: 'movie' (default) or 'tv'.
        page: Page number (default 1).
    """
    try:
        if media_type == "tv":
            result = await tmdb_api.get_popular_tv(page=page)
        else:
            result = await tmdb_api.get_popular_movies(page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🔥 Popular {media_type}s:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_top_rated(media_type: str = "movie", page: int = 1) -> str:
    """
    Get top-rated movies or TV shows of all time.

    Args:
        media_type: 'movie' (default) or 'tv'.
        page: Page number (default 1).
    """
    try:
        if media_type == "tv":
            result = await tmdb_api.get_top_rated_tv(page=page)
        else:
            result = await tmdb_api.get_top_rated_movies(page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"⭐ Top rated {media_type}s:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_now_playing(page: int = 1) -> str:
    """
    Get movies currently playing in theatres. Movie-only.

    Args:
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_now_playing_movies(page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎬 Now playing in theatres:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_upcoming_movies(page: int = 1) -> str:
    """
    Get movies that are coming soon / upcoming releases.

    Args:
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_upcoming_movies(page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🔜 Upcoming movies:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_get_airing_today(page: int = 1) -> str:
    """
    Get TV shows that have episodes airing today.

    Args:
        page: Page number (default 1).
    """
    try:
        result = await tmdb_api.get_airing_today_tv(page=page)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📺 TV shows airing today:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# GENRES & KEYWORDS (for discover filters)
# ===================================================================

@tool
async def tmdb_get_genres(media_type: str = "movie") -> str:
    """
    Get the full list of genre IDs and names for movies or TV.
    Call this before using tmdb_discover_movies/tmdb_discover_tv to look
    up the correct genre IDs (e.g. Action = 28, Comedy = 35 for movies).

    Args:
        media_type: 'movie' (default) or 'tv'.
    """
    try:
        if media_type == "tv":
            result = await tmdb_api.get_tv_genres()
        else:
            result = await tmdb_api.get_movie_genres()
        if isinstance(result, dict) and "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎭 {media_type.title()} genres:\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def tmdb_search_keyword(query: str) -> str:
    """
    Search for TMDB keywords by name. Use these keyword IDs with the
    discover tools to filter by thematic keywords (e.g. 'time travel',
    'heist', 'dystopia').

    Args:
        query: Keyword to search for (e.g. 'zombie', 'space').
    """
    try:
        result = await tmdb_api.search_keyword(query)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🔑 Keywords matching '{query}':\n{_fmt(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# EXPORT: All tools grouped for easy registration
# ===================================================================

tmdb_tools = [
    # Search
    tmdb_search,
    # Movie details
    tmdb_get_movie,
    tmdb_get_movie_credits,
    tmdb_get_movie_recommendations,
    tmdb_get_movie_reviews,
    tmdb_get_movie_videos,
    tmdb_get_movie_watch_providers,
    # TV show details
    tmdb_get_tv_show,
    tmdb_get_tv_credits,
    tmdb_get_tv_recommendations,
    tmdb_get_tv_reviews,
    tmdb_get_tv_videos,
    tmdb_get_tv_watch_providers,
    tmdb_get_tv_season,
    # Person details
    tmdb_get_person,
    tmdb_get_person_movie_credits,
    tmdb_get_person_tv_credits,
    # Trending & Browse
    tmdb_get_trending,
    tmdb_discover_movies,
    tmdb_discover_tv,
    tmdb_get_popular,
    tmdb_get_top_rated,
    tmdb_get_now_playing,
    tmdb_get_upcoming_movies,
    tmdb_get_airing_today,
    # Genres & Keywords (helpers for discover)
    tmdb_get_genres,
    tmdb_search_keyword,
]
