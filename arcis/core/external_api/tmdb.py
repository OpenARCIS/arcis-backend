from typing import Any, Dict, List, Optional

import httpx

from arcis import Config
from arcis.logger import LOGGER


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


# ---------------------------------------------------------------------------
# Helpers — extract only the fields an LLM actually needs
# ---------------------------------------------------------------------------

def _img_url(path: Optional[str], size: str = "w500") -> Optional[str]:
    """Build a full TMDB image URL from a relative path."""
    return f"{TMDB_IMAGE_BASE}/{size}{path}" if path else None


def _simplify_movie(m: dict) -> dict:
    """Distill a TMDB movie object into an LLM-friendly dict."""
    if not m:
        return {}
    return {
        "id": m.get("id"),
        "title": m.get("title"),
        "original_title": m.get("original_title"),
        "release_date": m.get("release_date"),
        "overview": (m.get("overview") or "")[:500],
        "vote_average": m.get("vote_average"),
        "vote_count": m.get("vote_count"),
        "popularity": m.get("popularity"),
        "genre_ids": m.get("genre_ids"),
        "original_language": m.get("original_language"),
        "adult": m.get("adult"),
        "poster": _img_url(m.get("poster_path")),
        "backdrop": _img_url(m.get("backdrop_path"), "w780"),
    }


def _simplify_tv(t: dict) -> dict:
    """Distill a TMDB TV show object into an LLM-friendly dict."""
    if not t:
        return {}
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "original_name": t.get("original_name"),
        "first_air_date": t.get("first_air_date"),
        "overview": (t.get("overview") or "")[:500],
        "vote_average": t.get("vote_average"),
        "vote_count": t.get("vote_count"),
        "popularity": t.get("popularity"),
        "genre_ids": t.get("genre_ids"),
        "original_language": t.get("original_language"),
        "origin_country": t.get("origin_country"),
        "poster": _img_url(t.get("poster_path")),
        "backdrop": _img_url(t.get("backdrop_path"), "w780"),
    }


def _simplify_person(p: dict) -> dict:
    """Distill a TMDB person object into an LLM-friendly dict."""
    if not p:
        return {}
    # known_for may contain movies or TV — simplify them too
    known_for = []
    for item in (p.get("known_for") or []):
        media_type = item.get("media_type")
        if media_type == "movie":
            known_for.append({**_simplify_movie(item), "media_type": "movie"})
        elif media_type == "tv":
            known_for.append({**_simplify_tv(item), "media_type": "tv"})
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "known_for_department": p.get("known_for_department"),
        "popularity": p.get("popularity"),
        "gender": p.get("gender"),
        "profile_image": _img_url(p.get("profile_path"), "w185"),
        "known_for": known_for if known_for else None,
    }


def _simplify_cast(c: dict) -> dict:
    """Simplify a cast member from a credits response."""
    if not c:
        return {}
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "character": c.get("character"),
        "order": c.get("order"),
        "known_for_department": c.get("known_for_department"),
        "profile_image": _img_url(c.get("profile_path"), "w185"),
    }


def _simplify_crew(c: dict) -> dict:
    """Simplify a crew member from a credits response."""
    if not c:
        return {}
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "job": c.get("job"),
        "department": c.get("department"),
        "profile_image": _img_url(c.get("profile_path"), "w185"),
    }


def _simplify_movie_detail(m: dict) -> dict:
    """Full movie detail with genres expanded, runtime, etc."""
    if not m:
        return {}
    genres = [{"id": g["id"], "name": g["name"]} for g in (m.get("genres") or [])]
    production = [c.get("name") for c in (m.get("production_companies") or [])]
    return {
        "id": m.get("id"),
        "title": m.get("title"),
        "original_title": m.get("original_title"),
        "tagline": m.get("tagline"),
        "overview": (m.get("overview") or "")[:800],
        "release_date": m.get("release_date"),
        "runtime": m.get("runtime"),
        "status": m.get("status"),
        "genres": genres,
        "vote_average": m.get("vote_average"),
        "vote_count": m.get("vote_count"),
        "popularity": m.get("popularity"),
        "budget": m.get("budget"),
        "revenue": m.get("revenue"),
        "original_language": m.get("original_language"),
        "spoken_languages": [
            l.get("english_name") for l in (m.get("spoken_languages") or [])
        ],
        "production_companies": production,
        "homepage": m.get("homepage"),
        "imdb_id": m.get("imdb_id"),
        "poster": _img_url(m.get("poster_path")),
        "backdrop": _img_url(m.get("backdrop_path"), "w780"),
    }


def _simplify_tv_detail(t: dict) -> dict:
    """Full TV show detail with seasons, creators, etc."""
    if not t:
        return {}
    genres = [{"id": g["id"], "name": g["name"]} for g in (t.get("genres") or [])]
    creators = [
        {"id": c.get("id"), "name": c.get("name")}
        for c in (t.get("created_by") or [])
    ]
    seasons = [
        {
            "season_number": s.get("season_number"),
            "name": s.get("name"),
            "episode_count": s.get("episode_count"),
            "air_date": s.get("air_date"),
            "overview": (s.get("overview") or "")[:200],
        }
        for s in (t.get("seasons") or [])
    ]
    networks = [n.get("name") for n in (t.get("networks") or [])]
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "original_name": t.get("original_name"),
        "tagline": t.get("tagline"),
        "overview": (t.get("overview") or "")[:800],
        "first_air_date": t.get("first_air_date"),
        "last_air_date": t.get("last_air_date"),
        "status": t.get("status"),
        "type": t.get("type"),
        "number_of_seasons": t.get("number_of_seasons"),
        "number_of_episodes": t.get("number_of_episodes"),
        "episode_run_time": t.get("episode_run_time"),
        "genres": genres,
        "created_by": creators,
        "networks": networks,
        "vote_average": t.get("vote_average"),
        "vote_count": t.get("vote_count"),
        "popularity": t.get("popularity"),
        "original_language": t.get("original_language"),
        "origin_country": t.get("origin_country"),
        "homepage": t.get("homepage"),
        "seasons": seasons,
        "poster": _img_url(t.get("poster_path")),
        "backdrop": _img_url(t.get("backdrop_path"), "w780"),
    }


def _simplify_season_detail(s: dict) -> dict:
    """Season detail with episode list."""
    if not s:
        return {}
    episodes = [
        {
            "episode_number": ep.get("episode_number"),
            "name": ep.get("name"),
            "air_date": ep.get("air_date"),
            "overview": (ep.get("overview") or "")[:300],
            "vote_average": ep.get("vote_average"),
            "runtime": ep.get("runtime"),
            "still": _img_url(ep.get("still_path"), "w300"),
        }
        for ep in (s.get("episodes") or [])
    ]
    return {
        "id": s.get("id"),
        "name": s.get("name"),
        "season_number": s.get("season_number"),
        "air_date": s.get("air_date"),
        "overview": (s.get("overview") or "")[:500],
        "episode_count": len(episodes),
        "episodes": episodes,
        "poster": _img_url(s.get("poster_path")),
    }


def _simplify_person_detail(p: dict) -> dict:
    """Full person detail."""
    if not p:
        return {}
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "biography": (p.get("biography") or "")[:1000],
        "birthday": p.get("birthday"),
        "deathday": p.get("deathday"),
        "place_of_birth": p.get("place_of_birth"),
        "known_for_department": p.get("known_for_department"),
        "popularity": p.get("popularity"),
        "gender": p.get("gender"),
        "homepage": p.get("homepage"),
        "imdb_id": p.get("imdb_id"),
        "profile_image": _img_url(p.get("profile_path"), "w185"),
    }


# ---------------------------------------------------------------------------
# Main wrapper class
# ---------------------------------------------------------------------------

class TMDBAPI:
    """Async TMDB v3 API wrapper for LLM tool-use."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or Config.TMDB_API_KEY
        if not self._api_key:
            raise ValueError(
                "TMDB API key is required. "
                "Set TMDB_API_KEY in your environment."
            )

    # -----------------------------------------------------------------------
    # Core HTTP helper
    # -----------------------------------------------------------------------

    async def _get(self, path: str, **params) -> Dict[str, Any]:
        """
        Make a GET request to the TMDB v3 API.

        Returns the parsed JSON body, or a standardised error dict
        ``{"error": "...", "status_code": N}``.
        """
        params["api_key"] = self._api_key
        url = f"{TMDB_API_BASE}/{path.lstrip('/')}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params=params,
                timeout=15.0,
            )

        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code >= 400:
            err_msg = data.get("status_message", resp.text[:300])
            LOGGER.error(f"TMDB: {resp.status_code} — {err_msg}")
            return {"error": err_msg, "status_code": resp.status_code}

        return data

    # ===================================================================
    # SEARCH (Multi, Movies, TV, People)
    # ===================================================================

    async def search_multi(
        self,
        query: str,
        page: int = 1,
        include_adult: bool = False,
        language: str = "en-US",
    ) -> Dict[str, Any]:
        """
        Search across movies, TV shows, and people in a single call.

        Args:
            query:          Free-text search string.
            page:           Page number (1-based, default 1).
            include_adult:  Include adult content in results.
            language:       ISO 639-1 language code (default en-US).

        Returns:
            Dict with keys: query, page, total_pages, total_results,
            movies, tv_shows, people.
        """
        raw = await self._get(
            "search/multi",
            query=query,
            page=page,
            include_adult=str(include_adult).lower(),
            language=language,
        )
        if "error" in raw:
            return raw

        movies, tv_shows, people = [], [], []
        for item in raw.get("results", []):
            media_type = item.get("media_type")
            if media_type == "movie":
                movies.append(_simplify_movie(item))
            elif media_type == "tv":
                tv_shows.append(_simplify_tv(item))
            elif media_type == "person":
                people.append(_simplify_person(item))

        return {
            "query": query,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "movies": movies if movies else None,
            "tv_shows": tv_shows if tv_shows else None,
            "people": people if people else None,
        }

    async def search_movies(
        self,
        query: str,
        page: int = 1,
        year: Optional[int] = None,
        primary_release_year: Optional[int] = None,
        include_adult: bool = False,
        language: str = "en-US",
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search specifically for movies.

        Args:
            query:                  Search string.
            page:                   Page number.
            year:                   Filter by year (searches release dates).
            primary_release_year:   Filter by primary release year.
            include_adult:          Include adult content.
            language:               Language code (default en-US).
            region:                 ISO 3166-1 region code to filter releases.
        """
        params = {
            "query": query,
            "page": page,
            "include_adult": str(include_adult).lower(),
            "language": language,
        }
        if year:
            params["year"] = year
        if primary_release_year:
            params["primary_release_year"] = primary_release_year
        if region:
            params["region"] = region

        raw = await self._get("search/movie", **params)
        if "error" in raw:
            return raw

        return {
            "query": query,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def search_tv(
        self,
        query: str,
        page: int = 1,
        first_air_date_year: Optional[int] = None,
        include_adult: bool = False,
        language: str = "en-US",
    ) -> Dict[str, Any]:
        """Search specifically for TV shows."""
        params = {
            "query": query,
            "page": page,
            "include_adult": str(include_adult).lower(),
            "language": language,
        }
        if first_air_date_year:
            params["first_air_date_year"] = first_air_date_year

        raw = await self._get("search/tv", **params)
        if "error" in raw:
            return raw

        return {
            "query": query,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    async def search_person(
        self,
        query: str,
        page: int = 1,
        include_adult: bool = False,
        language: str = "en-US",
    ) -> Dict[str, Any]:
        """Search specifically for people (actors, directors, etc.)."""
        params = {
            "query": query,
            "page": page,
            "include_adult": str(include_adult).lower(),
            "language": language,
        }

        raw = await self._get("search/person", **params)
        if "error" in raw:
            return raw

        return {
            "query": query,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "results": [_simplify_person(p) for p in raw.get("results", [])],
        }

    # ===================================================================
    # MOVIE DETAILS
    # ===================================================================

    async def get_movie(self, movie_id: int, language: str = "en-US") -> dict:
        """Get full details for a movie."""
        raw = await self._get(f"movie/{movie_id}", language=language)
        return raw if "error" in raw else _simplify_movie_detail(raw)

    async def get_movie_credits(self, movie_id: int, language: str = "en-US") -> dict:
        """Get cast and crew for a movie."""
        raw = await self._get(f"movie/{movie_id}/credits", language=language)
        if "error" in raw:
            return raw
        cast = [_simplify_cast(c) for c in raw.get("cast", [])[:20]]
        # Only key crew: directors, writers, producers
        key_jobs = {"Director", "Writer", "Screenplay", "Producer", "Executive Producer"}
        crew = [
            _simplify_crew(c)
            for c in raw.get("crew", [])
            if c.get("job") in key_jobs
        ]
        return {"movie_id": movie_id, "cast": cast, "crew": crew}

    async def get_movie_recommendations(
        self, movie_id: int, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get movies recommended based on a specific movie."""
        raw = await self._get(
            f"movie/{movie_id}/recommendations", page=page, language=language,
        )
        if "error" in raw:
            return raw
        return {
            "source_movie_id": movie_id,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def get_similar_movies(
        self, movie_id: int, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get movies similar to a specific movie."""
        raw = await self._get(
            f"movie/{movie_id}/similar", page=page, language=language,
        )
        if "error" in raw:
            return raw
        return {
            "source_movie_id": movie_id,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def get_movie_reviews(
        self, movie_id: int, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get user reviews for a movie."""
        raw = await self._get(
            f"movie/{movie_id}/reviews", page=page, language=language,
        )
        if "error" in raw:
            return raw
        reviews = [
            {
                "author": r.get("author"),
                "rating": (r.get("author_details") or {}).get("rating"),
                "content": (r.get("content") or "")[:600],
                "created_at": r.get("created_at"),
                "url": r.get("url"),
            }
            for r in raw.get("results", [])[:10]
        ]
        return {
            "movie_id": movie_id,
            "page": raw.get("page"),
            "total_results": raw.get("total_results"),
            "reviews": reviews,
        }

    async def get_movie_videos(
        self, movie_id: int, language: str = "en-US",
    ) -> dict:
        """Get videos (trailers, teasers, clips) for a movie."""
        raw = await self._get(f"movie/{movie_id}/videos", language=language)
        if "error" in raw:
            return raw
        videos = [
            {
                "name": v.get("name"),
                "type": v.get("type"),
                "site": v.get("site"),
                "key": v.get("key"),
                "url": (
                    f"https://www.youtube.com/watch?v={v['key']}"
                    if v.get("site") == "YouTube"
                    else None
                ),
                "official": v.get("official"),
                "published_at": v.get("published_at"),
            }
            for v in raw.get("results", [])
        ]
        return {"movie_id": movie_id, "videos": videos}

    async def get_movie_watch_providers(
        self, movie_id: int,
    ) -> dict:
        """
        Get where to watch a movie (streaming, rent, buy).
        Returns availability grouped by country.
        """
        raw = await self._get(f"movie/{movie_id}/watch/providers")
        if "error" in raw:
            return raw
        results = raw.get("results", {})
        # Return a few key regions to avoid token explosion
        simplified = {}
        for region_code in ("US", "GB", "IN", "CA", "AU", "DE", "FR"):
            region_data = results.get(region_code)
            if region_data:
                simplified[region_code] = {
                    "link": region_data.get("link"),
                    "stream": [
                        p.get("provider_name")
                        for p in (region_data.get("flatrate") or [])
                    ] or None,
                    "rent": [
                        p.get("provider_name")
                        for p in (region_data.get("rent") or [])
                    ] or None,
                    "buy": [
                        p.get("provider_name")
                        for p in (region_data.get("buy") or [])
                    ] or None,
                }
        return {"movie_id": movie_id, "providers": simplified}

    # ===================================================================
    # TV SHOW DETAILS
    # ===================================================================

    async def get_tv_show(self, tv_id: int, language: str = "en-US") -> dict:
        """Get full details for a TV show."""
        raw = await self._get(f"tv/{tv_id}", language=language)
        return raw if "error" in raw else _simplify_tv_detail(raw)

    async def get_tv_credits(self, tv_id: int, language: str = "en-US") -> dict:
        """Get cast and crew for a TV show."""
        raw = await self._get(f"tv/{tv_id}/credits", language=language)
        if "error" in raw:
            return raw
        cast = [_simplify_cast(c) for c in raw.get("cast", [])[:20]]
        key_jobs = {"Director", "Writer", "Creator", "Executive Producer", "Showrunner"}
        crew = [
            _simplify_crew(c)
            for c in raw.get("crew", [])
            if c.get("job") in key_jobs
        ]
        return {"tv_id": tv_id, "cast": cast, "crew": crew}

    async def get_tv_recommendations(
        self, tv_id: int, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get TV shows recommended based on a specific show."""
        raw = await self._get(
            f"tv/{tv_id}/recommendations", page=page, language=language,
        )
        if "error" in raw:
            return raw
        return {
            "source_tv_id": tv_id,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    async def get_similar_tv(
        self, tv_id: int, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get TV shows similar to a specific show."""
        raw = await self._get(
            f"tv/{tv_id}/similar", page=page, language=language,
        )
        if "error" in raw:
            return raw
        return {
            "source_tv_id": tv_id,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    async def get_tv_reviews(
        self, tv_id: int, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get user reviews for a TV show."""
        raw = await self._get(
            f"tv/{tv_id}/reviews", page=page, language=language,
        )
        if "error" in raw:
            return raw
        reviews = [
            {
                "author": r.get("author"),
                "rating": (r.get("author_details") or {}).get("rating"),
                "content": (r.get("content") or "")[:600],
                "created_at": r.get("created_at"),
                "url": r.get("url"),
            }
            for r in raw.get("results", [])[:10]
        ]
        return {
            "tv_id": tv_id,
            "page": raw.get("page"),
            "total_results": raw.get("total_results"),
            "reviews": reviews,
        }

    async def get_tv_videos(
        self, tv_id: int, language: str = "en-US",
    ) -> dict:
        """Get videos (trailers, teasers, clips) for a TV show."""
        raw = await self._get(f"tv/{tv_id}/videos", language=language)
        if "error" in raw:
            return raw
        videos = [
            {
                "name": v.get("name"),
                "type": v.get("type"),
                "site": v.get("site"),
                "key": v.get("key"),
                "url": (
                    f"https://www.youtube.com/watch?v={v['key']}"
                    if v.get("site") == "YouTube"
                    else None
                ),
                "official": v.get("official"),
                "published_at": v.get("published_at"),
            }
            for v in raw.get("results", [])
        ]
        return {"tv_id": tv_id, "videos": videos}

    async def get_tv_watch_providers(self, tv_id: int) -> dict:
        """Get where to watch a TV show (streaming, rent, buy)."""
        raw = await self._get(f"tv/{tv_id}/watch/providers")
        if "error" in raw:
            return raw
        results = raw.get("results", {})
        simplified = {}
        for region_code in ("US", "GB", "IN", "CA", "AU", "DE", "FR"):
            region_data = results.get(region_code)
            if region_data:
                simplified[region_code] = {
                    "link": region_data.get("link"),
                    "stream": [
                        p.get("provider_name")
                        for p in (region_data.get("flatrate") or [])
                    ] or None,
                    "rent": [
                        p.get("provider_name")
                        for p in (region_data.get("rent") or [])
                    ] or None,
                    "buy": [
                        p.get("provider_name")
                        for p in (region_data.get("buy") or [])
                    ] or None,
                }
        return {"tv_id": tv_id, "providers": simplified}

    async def get_tv_season(
        self, tv_id: int, season_number: int, language: str = "en-US",
    ) -> dict:
        """Get details for a specific season, including its episode list."""
        raw = await self._get(
            f"tv/{tv_id}/season/{season_number}", language=language,
        )
        return raw if "error" in raw else _simplify_season_detail(raw)

    # ===================================================================
    # PERSON DETAILS
    # ===================================================================

    async def get_person(self, person_id: int, language: str = "en-US") -> dict:
        """Get full details for a person."""
        raw = await self._get(f"person/{person_id}", language=language)
        return raw if "error" in raw else _simplify_person_detail(raw)

    async def get_person_movie_credits(
        self, person_id: int, language: str = "en-US",
    ) -> dict:
        """Get a person's movie credits (acting + crew)."""
        raw = await self._get(
            f"person/{person_id}/movie_credits", language=language,
        )
        if "error" in raw:
            return raw
        cast = [
            {**_simplify_movie(m), "character": m.get("character")}
            for m in sorted(
                raw.get("cast", []),
                key=lambda x: x.get("popularity", 0),
                reverse=True,
            )[:20]
        ]
        crew = [
            {**_simplify_movie(m), "job": m.get("job"), "department": m.get("department")}
            for m in sorted(
                raw.get("crew", []),
                key=lambda x: x.get("popularity", 0),
                reverse=True,
            )[:10]
        ]
        return {"person_id": person_id, "cast": cast, "crew": crew}

    async def get_person_tv_credits(
        self, person_id: int, language: str = "en-US",
    ) -> dict:
        """Get a person's TV credits (acting + crew)."""
        raw = await self._get(
            f"person/{person_id}/tv_credits", language=language,
        )
        if "error" in raw:
            return raw
        cast = [
            {**_simplify_tv(t), "character": t.get("character")}
            for t in sorted(
                raw.get("cast", []),
                key=lambda x: x.get("popularity", 0),
                reverse=True,
            )[:20]
        ]
        crew = [
            {**_simplify_tv(t), "job": t.get("job"), "department": t.get("department")}
            for t in sorted(
                raw.get("crew", []),
                key=lambda x: x.get("popularity", 0),
                reverse=True,
            )[:10]
        ]
        return {"person_id": person_id, "cast": cast, "crew": crew}

    # ===================================================================
    # TRENDING
    # ===================================================================

    async def get_trending(
        self,
        media_type: str = "all",
        time_window: str = "day",
        page: int = 1,
        language: str = "en-US",
    ) -> dict:
        """
        Get trending items.

        Args:
            media_type:   "all", "movie", "tv", or "person".
            time_window:  "day" or "week".
            page:         Page number.
            language:     Language code.
        """
        raw = await self._get(
            f"trending/{media_type}/{time_window}",
            page=page,
            language=language,
        )
        if "error" in raw:
            return raw

        results = []
        for item in raw.get("results", []):
            mt = item.get("media_type", media_type)
            if mt == "movie":
                results.append({**_simplify_movie(item), "media_type": "movie"})
            elif mt == "tv":
                results.append({**_simplify_tv(item), "media_type": "tv"})
            elif mt == "person":
                results.append({**_simplify_person(item), "media_type": "person"})

        return {
            "media_type": media_type,
            "time_window": time_window,
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "results": results,
        }

    # ===================================================================
    # DISCOVER — Advanced filtered browsing
    # ===================================================================

    async def discover_movies(
        self,
        page: int = 1,
        sort_by: str = "popularity.desc",
        with_genres: Optional[str] = None,
        primary_release_year: Optional[int] = None,
        primary_release_date_gte: Optional[str] = None,
        primary_release_date_lte: Optional[str] = None,
        vote_average_gte: Optional[float] = None,
        vote_count_gte: Optional[int] = None,
        with_original_language: Optional[str] = None,
        with_keywords: Optional[str] = None,
        without_genres: Optional[str] = None,
        include_adult: bool = False,
        language: str = "en-US",
        region: Optional[str] = None,
    ) -> dict:
        """
        Discover movies using a wide set of filters.

        Args:
            sort_by:                    Sort order. Options include:
                                        popularity.asc/desc, revenue.asc/desc,
                                        primary_release_date.asc/desc,
                                        vote_average.asc/desc, vote_count.asc/desc.
            with_genres:                Comma-separated genre IDs to include.
            primary_release_year:       Exact release year.
            primary_release_date_gte:   Release date >= (YYYY-MM-DD).
            primary_release_date_lte:   Release date <= (YYYY-MM-DD).
            vote_average_gte:           Minimum vote average (0-10).
            vote_count_gte:             Minimum number of votes.
            with_original_language:     ISO 639-1 language code (e.g. "en", "ko", "ja").
            with_keywords:              Comma-separated keyword IDs.
            without_genres:             Comma-separated genre IDs to exclude.
            include_adult:              Include adult content.
            language:                   Language for results.
            region:                     ISO 3166-1 region code.
        """
        params: Dict[str, Any] = {
            "page": page,
            "sort_by": sort_by,
            "include_adult": str(include_adult).lower(),
            "language": language,
        }
        if with_genres:
            params["with_genres"] = with_genres
        if primary_release_year:
            params["primary_release_year"] = primary_release_year
        if primary_release_date_gte:
            params["primary_release_date.gte"] = primary_release_date_gte
        if primary_release_date_lte:
            params["primary_release_date.lte"] = primary_release_date_lte
        if vote_average_gte is not None:
            params["vote_average.gte"] = vote_average_gte
        if vote_count_gte is not None:
            params["vote_count.gte"] = vote_count_gte
        if with_original_language:
            params["with_original_language"] = with_original_language
        if with_keywords:
            params["with_keywords"] = with_keywords
        if without_genres:
            params["without_genres"] = without_genres
        if region:
            params["region"] = region

        raw = await self._get("discover/movie", **params)
        if "error" in raw:
            return raw

        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def discover_tv(
        self,
        page: int = 1,
        sort_by: str = "popularity.desc",
        with_genres: Optional[str] = None,
        first_air_date_year: Optional[int] = None,
        first_air_date_gte: Optional[str] = None,
        first_air_date_lte: Optional[str] = None,
        vote_average_gte: Optional[float] = None,
        vote_count_gte: Optional[int] = None,
        with_original_language: Optional[str] = None,
        with_keywords: Optional[str] = None,
        without_genres: Optional[str] = None,
        include_adult: bool = False,
        language: str = "en-US",
    ) -> dict:
        """
        Discover TV shows using a wide set of filters.

        Args:
            sort_by:                  Sort order (popularity.desc, vote_average.desc, etc.).
            with_genres:              Comma-separated genre IDs.
            first_air_date_year:      Exact first air date year.
            first_air_date_gte:       First air date >= (YYYY-MM-DD).
            first_air_date_lte:       First air date <= (YYYY-MM-DD).
            vote_average_gte:         Minimum vote average.
            vote_count_gte:           Minimum number of votes.
            with_original_language:   Language code (e.g. "en", "ko").
            with_keywords:            Comma-separated keyword IDs.
            without_genres:           Comma-separated genre IDs to exclude.
            include_adult:            Include adult content.
            language:                 Language for results.
        """
        params: Dict[str, Any] = {
            "page": page,
            "sort_by": sort_by,
            "include_adult": str(include_adult).lower(),
            "language": language,
        }
        if with_genres:
            params["with_genres"] = with_genres
        if first_air_date_year:
            params["first_air_date_year"] = first_air_date_year
        if first_air_date_gte:
            params["first_air_date.gte"] = first_air_date_gte
        if first_air_date_lte:
            params["first_air_date.lte"] = first_air_date_lte
        if vote_average_gte is not None:
            params["vote_average.gte"] = vote_average_gte
        if vote_count_gte is not None:
            params["vote_count.gte"] = vote_count_gte
        if with_original_language:
            params["with_original_language"] = with_original_language
        if with_keywords:
            params["with_keywords"] = with_keywords
        if without_genres:
            params["without_genres"] = without_genres

        raw = await self._get("discover/tv", **params)
        if "error" in raw:
            return raw

        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "total_results": raw.get("total_results"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    # ===================================================================
    # GENRE LISTS
    # ===================================================================

    async def get_movie_genres(self, language: str = "en-US") -> list:
        """Get the official list of movie genre IDs and names."""
        raw = await self._get("genre/movie/list", language=language)
        if "error" in raw:
            return raw
        return raw.get("genres", [])

    async def get_tv_genres(self, language: str = "en-US") -> list:
        """Get the official list of TV genre IDs and names."""
        raw = await self._get("genre/tv/list", language=language)
        if "error" in raw:
            return raw
        return raw.get("genres", [])

    # ===================================================================
    # POPULAR / TOP-RATED / NOW-PLAYING / UPCOMING (Curated lists)
    # ===================================================================

    async def get_popular_movies(
        self, page: int = 1, language: str = "en-US", region: Optional[str] = None,
    ) -> dict:
        """Get currently popular movies."""
        params = {"page": page, "language": language}
        if region:
            params["region"] = region
        raw = await self._get("movie/popular", **params)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def get_top_rated_movies(
        self, page: int = 1, language: str = "en-US", region: Optional[str] = None,
    ) -> dict:
        """Get top-rated movies of all time."""
        params = {"page": page, "language": language}
        if region:
            params["region"] = region
        raw = await self._get("movie/top_rated", **params)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def get_now_playing_movies(
        self, page: int = 1, language: str = "en-US", region: Optional[str] = None,
    ) -> dict:
        """Get movies currently in theatres."""
        params = {"page": page, "language": language}
        if region:
            params["region"] = region
        raw = await self._get("movie/now_playing", **params)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def get_upcoming_movies(
        self, page: int = 1, language: str = "en-US", region: Optional[str] = None,
    ) -> dict:
        """Get upcoming movies."""
        params = {"page": page, "language": language}
        if region:
            params["region"] = region
        raw = await self._get("movie/upcoming", **params)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_movie(m) for m in raw.get("results", [])],
        }

    async def get_popular_tv(
        self, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get currently popular TV shows."""
        raw = await self._get("tv/popular", page=page, language=language)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    async def get_top_rated_tv(
        self, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get top-rated TV shows of all time."""
        raw = await self._get("tv/top_rated", page=page, language=language)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    async def get_on_the_air_tv(
        self, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get TV shows currently on the air (have episodes airing this week)."""
        raw = await self._get("tv/on_the_air", page=page, language=language)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    async def get_airing_today_tv(
        self, page: int = 1, language: str = "en-US",
    ) -> dict:
        """Get TV shows airing today."""
        raw = await self._get("tv/airing_today", page=page, language=language)
        if "error" in raw:
            return raw
        return {
            "page": raw.get("page"),
            "total_pages": raw.get("total_pages"),
            "results": [_simplify_tv(t) for t in raw.get("results", [])],
        }

    # ===================================================================
    # KEYWORD SEARCH (for discover filters)
    # ===================================================================

    async def search_keyword(self, query: str, page: int = 1) -> dict:
        """
        Search for TMDB keywords.  Keyword IDs can then be passed to
        discover_movies/discover_tv via ``with_keywords``.
        """
        raw = await self._get("search/keyword", query=query, page=page)
        if "error" in raw:
            return raw
        return {
            "query": query,
            "page": raw.get("page"),
            "total_results": raw.get("total_results"),
            "results": [
                {"id": k.get("id"), "name": k.get("name")}
                for k in raw.get("results", [])
            ],
        }


# ---------------------------------------------------------------------------
# Lazy singleton — created on first use so missing key doesn't crash at import
# ---------------------------------------------------------------------------

_instance: Optional[TMDBAPI] = None


def _get_instance() -> TMDBAPI:
    global _instance
    if _instance is None:
        _instance = TMDBAPI()
    return _instance


class _LazyProxy:
    """Proxy that defers TMDBAPI construction until first attribute access."""

    def __getattr__(self, name):
        return getattr(_get_instance(), name)


tmdb_api = _LazyProxy()
