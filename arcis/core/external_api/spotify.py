"""
Spotify Web API — Async Wrapper for ARCIS.

Full-control wrapper over a user's Spotify account.  Every public method
returns a plain dict that a reasoning LLM can consume as a tool result,
so it can iterate, branch, and compose calls autonomously.

Auth tokens are persisted in MongoDB (field ``spotify_credentials`` on the
user document), exactly like the Google/Gmail wrappers.

Requirements: httpx (already in requirements.txt).
"""

import time
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from arcis import Config
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.models.errors import SpotifyAuthError
from arcis.logger import LOGGER


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Comprehensive scopes for full account control
SPOTIFY_SCOPES = [
    # Listening history
    "user-read-recently-played",
    "user-top-read",
    "user-read-playback-position",
    # Spotify Connect
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    # Playlists
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
    # Library
    "user-library-read",
    "user-library-modify",
    # User profile
    "user-read-email",
    "user-read-private",
    # Follow
    "user-follow-read",
    "user-follow-modify",
]


# ---------------------------------------------------------------------------
# Helpers — extract only the fields an LLM actually needs
# ---------------------------------------------------------------------------

def _simplify_track(t: dict) -> dict:
    """Distill a Spotify track object into an LLM-friendly dict."""
    if not t:
        return {}
    artists = [{"id": a["id"], "name": a["name"]} for a in t.get("artists", [])]
    album = t.get("album") or {}
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "artists": artists,
        "album": {"id": album.get("id"), "name": album.get("name")} if album else None,
        "duration_ms": t.get("duration_ms"),
        "uri": t.get("uri"),
        "explicit": t.get("explicit"),
        "popularity": t.get("popularity"),
        "preview_url": t.get("preview_url"),
        "track_number": t.get("track_number"),
        "is_playable": t.get("is_playable"),
    }


def _simplify_album(a: dict) -> dict:
    if not a:
        return {}
    artists = [{"id": ar["id"], "name": ar["name"]} for ar in a.get("artists", [])]
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "artists": artists,
        "release_date": a.get("release_date"),
        "total_tracks": a.get("total_tracks"),
        "uri": a.get("uri"),
        "album_type": a.get("album_type"),
        "images": a.get("images", [])[:1],  # just the largest image
    }


def _simplify_artist(ar: dict) -> dict:
    if not ar:
        return {}
    return {
        "id": ar.get("id"),
        "name": ar.get("name"),
        "genres": ar.get("genres", []),
        "popularity": ar.get("popularity"),
        "uri": ar.get("uri"),
        "followers": ar.get("followers", {}).get("total"),
        "images": ar.get("images", [])[:1],
    }


def _simplify_playlist(p: dict) -> dict:
    if not p:
        return {}
    owner = p.get("owner") or {}
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "description": p.get("description"),
        "owner": {"id": owner.get("id"), "display_name": owner.get("display_name")},
        "public": p.get("public"),
        "collaborative": p.get("collaborative"),
        "total_tracks": (p.get("tracks") or {}).get("total"),
        "uri": p.get("uri"),
        "images": p.get("images", [])[:1],
    }


def _simplify_device(d: dict) -> dict:
    if not d:
        return {}
    return {
        "id": d.get("id"),
        "name": d.get("name"),
        "type": d.get("type"),
        "is_active": d.get("is_active"),
        "volume_percent": d.get("volume_percent"),
    }


# ---------------------------------------------------------------------------
# Main wrapper class
# ---------------------------------------------------------------------------

class SpotifyAPI:
    """Async Spotify Web API wrapper for LLM tool-use."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._username: str = "test_user"

    # -----------------------------------------------------------------------
    # Credential management (MongoDB-backed, like GoogleAPI)
    # -----------------------------------------------------------------------

    async def load_creds(self, username: str = "test_user"):
        """Load stored Spotify credentials from MongoDB."""
        self._username = username
        user = await mongo.db[COLLECTIONS["users"]].find_one({"username": username})
        if not user:
            raise SpotifyAuthError("User not found in database.")

        creds = user.get("spotify_credentials")
        if not creds:
            raise SpotifyAuthError(
                "Spotify credentials not found. Complete OAuth flow first."
            )

        self._access_token = creds.get("access_token")
        self._refresh_token = creds.get("refresh_token")
        self._token_expiry = creds.get("token_expiry", 0.0)

    async def save_creds(self, username: Optional[str] = None):
        """Persist the current token set back to MongoDB."""
        username = username or self._username
        payload = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "token_expiry": self._token_expiry,
        }
        await mongo.db[COLLECTIONS["users"]].update_one(
            {"username": username},
            {"$set": {"spotify_credentials": payload}},
            upsert=True,
        )

    # -----------------------------------------------------------------------
    # OAuth helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def get_auth_url(state: Optional[str] = None) -> str:
        """
        Build the Spotify authorization URL the user must visit to grant
        permissions.  Returns the full URL as a string.
        """
        params = {
            "client_id": Config.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": Config.SPOTIFY_REDIRECT_URI,
            "scope": " ".join(SPOTIFY_SCOPES),
        }
        if state:
            params["state"] = state
        return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str, username: str = "test_user"):
        """
        Exchange the authorization *code* received from the Spotify callback
        for access + refresh tokens.  Saves them to MongoDB automatically.

        Returns:
            dict with keys ``access_token``, ``refresh_token``, ``expires_in``
            on success, or ``{"error": "..."}`` on failure.
        """
        self._username = username
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": Config.SPOTIFY_REDIRECT_URI,
                    "client_id": Config.SPOTIFY_CLIENT_ID,
                    "client_secret": Config.SPOTIFY_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        data = resp.json()
        if resp.status_code != 200:
            LOGGER.error(f"SPOTIFY: Token exchange failed — {data}")
            return {"error": data.get("error_description", "Token exchange failed"),
                    "status_code": resp.status_code}

        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        await self.save_creds()

        LOGGER.info("SPOTIFY: OAuth tokens obtained and saved.")
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_in": data.get("expires_in"),
        }

    async def _refresh_access_token(self):
        """Silently refresh the access token using the stored refresh token."""
        if not self._refresh_token:
            raise SpotifyAuthError("No refresh token available. Re-authenticate.")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": Config.SPOTIFY_CLIENT_ID,
                    "client_secret": Config.SPOTIFY_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        data = resp.json()
        if resp.status_code != 200:
            LOGGER.error(f"SPOTIFY: Token refresh failed — {data}")
            raise SpotifyAuthError(
                data.get("error_description", "Token refresh failed")
            )

        self._access_token = data["access_token"]
        # Spotify may rotate the refresh token
        if "refresh_token" in data:
            self._refresh_token = data["refresh_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        await self.save_creds()
        LOGGER.info("SPOTIFY: Access token refreshed.")

    # -----------------------------------------------------------------------
    # Core HTTP helper — every API call goes through here
    # -----------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        base_url: str = SPOTIFY_API_BASE,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Spotify Web API.

        Automatically refreshes the token if it is expired or about to expire
        (within 60 s).  Returns the parsed JSON body, or a standardised error
        dict ``{"error": "...", "status_code": N}``.
        """
        # Auto-refresh if token is stale
        if time.time() >= (self._token_expiry - 60):
            await self._refresh_access_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = f"{base_url}/{path.lstrip('/')}" if not path.startswith("http") else path

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, url, headers=headers, params=params, json=json_body,
                timeout=15.0,
            )

        # 204 No Content — success with empty body (e.g. playback commands)
        if resp.status_code == 204:
            return {"success": True}

        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code >= 400:
            err = data.get("error", {})
            err_msg = err.get("message", resp.text[:200]) if isinstance(err, dict) else str(err)
            LOGGER.error(f"SPOTIFY: {method} {path} → {resp.status_code} {err_msg}")
            return {"error": err_msg, "status_code": resp.status_code}

        return data

    # convenience aliases
    async def _get(self, path: str, **params) -> dict:
        return await self._request("GET", path, params=params or None)

    async def _post(self, path: str, json_body: Optional[dict] = None, **params) -> dict:
        return await self._request("POST", path, params=params or None, json_body=json_body)

    async def _put(self, path: str, json_body: Optional[dict] = None, **params) -> dict:
        return await self._request("PUT", path, params=params or None, json_body=json_body)

    async def _delete(self, path: str, json_body: Optional[dict] = None, **params) -> dict:
        return await self._request("DELETE", path, params=params or None, json_body=json_body)

    # ===================================================================
    # SEARCH
    # ===================================================================

    async def search(
        self,
        query: str,
        types: str = "track",
        limit: int = 10,
        market: str = "US",
        offset: int = 0,
    ) -> dict:
        """
        Search Spotify catalogue.

        Args:
            query:  Free-text search string.
            types:  Comma-separated list of item types to search across.
                    Valid values: track, album, artist, playlist, show, episode.
            limit:  Max results per type (1-50).
            market: ISO 3166-1 alpha-2 country code.
            offset: Pagination offset.

        Returns:
            Dict keyed by result type, each containing a list of simplified items.
        """
        raw = await self._get(
            "search", q=query, type=types, limit=limit, market=market, offset=offset,
        )
        if "error" in raw:
            return raw

        result: Dict[str, list] = {}
        simplifiers = {
            "tracks": _simplify_track,
            "albums": _simplify_album,
            "artists": _simplify_artist,
            "playlists": _simplify_playlist,
        }
        for key, fn in simplifiers.items():
            section = raw.get(key)
            if section:
                result[key] = [fn(item) for item in section.get("items", [])]

        # shows / episodes — pass through with minimal trimming
        for key in ("shows", "episodes"):
            section = raw.get(key)
            if section:
                result[key] = section.get("items", [])

        return result

    # ===================================================================
    # TRACKS
    # ===================================================================

    async def get_track(self, track_id: str, market: str = "US") -> dict:
        """Get details for a single track."""
        raw = await self._get(f"tracks/{track_id}", market=market)
        return raw if "error" in raw else _simplify_track(raw)

    async def get_several_tracks(self, track_ids: List[str], market: str = "US") -> list:
        """Get details for up to 50 tracks at once."""
        raw = await self._get("tracks", ids=",".join(track_ids[:50]), market=market)
        if "error" in raw:
            return raw
        return [_simplify_track(t) for t in raw.get("tracks", [])]

    async def get_audio_features(self, track_id: str) -> dict:
        """
        Get audio features for a track (tempo, energy, danceability, etc.).
        Useful for building recommendations or mood-based playlists.
        """
        return await self._get(f"audio-features/{track_id}")

    async def get_several_audio_features(self, track_ids: List[str]) -> list:
        """Get audio features for up to 100 tracks."""
        raw = await self._get("audio-features", ids=",".join(track_ids[:100]))
        if "error" in raw:
            return raw
        return raw.get("audio_features", [])

    # ===================================================================
    # ALBUMS
    # ===================================================================

    async def get_album(self, album_id: str, market: str = "US") -> dict:
        """Get album details including its track listing."""
        raw = await self._get(f"albums/{album_id}", market=market)
        if "error" in raw:
            return raw
        result = _simplify_album(raw)
        tracks_section = raw.get("tracks", {})
        result["tracks"] = [_simplify_track(t) for t in tracks_section.get("items", [])]
        return result

    async def get_album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0, market: str = "US",
    ) -> dict:
        """Get just the tracks of an album with pagination."""
        raw = await self._get(
            f"albums/{album_id}/tracks", limit=limit, offset=offset, market=market,
        )
        if "error" in raw:
            return raw
        return {
            "items": [_simplify_track(t) for t in raw.get("items", [])],
            "total": raw.get("total"),
            "next": raw.get("next"),
        }

    # ===================================================================
    # ARTISTS
    # ===================================================================

    async def get_artist(self, artist_id: str) -> dict:
        """Get artist details."""
        raw = await self._get(f"artists/{artist_id}")
        return raw if "error" in raw else _simplify_artist(raw)

    async def get_artist_top_tracks(self, artist_id: str, market: str = "US") -> list:
        """Get an artist's top tracks in a given market."""
        raw = await self._get(f"artists/{artist_id}/top-tracks", market=market)
        if "error" in raw:
            return raw
        return [_simplify_track(t) for t in raw.get("tracks", [])]

    async def get_artist_albums(
        self,
        artist_id: str,
        include_groups: str = "album,single",
        limit: int = 20,
        offset: int = 0,
        market: str = "US",
    ) -> dict:
        """Get an artist's albums/singles/compilations."""
        raw = await self._get(
            f"artists/{artist_id}/albums",
            include_groups=include_groups, limit=limit, offset=offset, market=market,
        )
        if "error" in raw:
            return raw
        return {
            "items": [_simplify_album(a) for a in raw.get("items", [])],
            "total": raw.get("total"),
            "next": raw.get("next"),
        }

    async def get_related_artists(self, artist_id: str) -> list:
        """Get artists similar to a given artist."""
        raw = await self._get(f"artists/{artist_id}/related-artists")
        if "error" in raw:
            return raw
        return [_simplify_artist(a) for a in raw.get("artists", [])]

    # ===================================================================
    # PLAYLISTS
    # ===================================================================

    async def get_playlist(
        self, playlist_id: str, limit: int = 100, offset: int = 0, market: str = "US",
    ) -> dict:
        """Get a playlist and its tracks."""
        raw = await self._get(
            f"playlists/{playlist_id}",
            market=market,
            fields="id,name,description,owner(id,display_name),public,collaborative,"
                   "images,tracks.total,tracks.items(track(id,name,artists(id,name),"
                   "album(id,name),duration_ms,uri,explicit,popularity)),tracks.next",
            limit=limit, offset=offset,
        )
        if "error" in raw:
            return raw

        result = _simplify_playlist(raw)
        tracks_section = raw.get("tracks", {})
        result["tracks"] = [
            _simplify_track(item.get("track", {}))
            for item in tracks_section.get("items", [])
            if item.get("track")
        ]
        result["tracks_next"] = tracks_section.get("next")
        return result

    async def get_current_user_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        """Get the authenticated user's playlists."""
        raw = await self._get("me/playlists", limit=limit, offset=offset)
        if "error" in raw:
            return raw
        return {
            "items": [_simplify_playlist(p) for p in raw.get("items", [])],
            "total": raw.get("total"),
            "next": raw.get("next"),
        }

    async def create_playlist(
        self,
        name: str,
        description: str = "",
        public: bool = True,
    ) -> dict:
        """Create a new playlist for the authenticated user."""
        # need user id first
        me = await self._get("me")
        if "error" in me:
            return me
        user_id = me.get("id")
        raw = await self._post(
            f"users/{user_id}/playlists",
            json_body={"name": name, "description": description, "public": public},
        )
        return raw if "error" in raw else _simplify_playlist(raw)

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_uris: List[str], position: Optional[int] = None,
    ) -> dict:
        """
        Add tracks to a playlist.

        Args:
            track_uris: List of Spotify URIs (``spotify:track:<id>``).
            position:  Optional 0-based position to insert at.
        """
        body: Dict[str, Any] = {"uris": track_uris[:100]}
        if position is not None:
            body["position"] = position
        return await self._post(f"playlists/{playlist_id}/tracks", json_body=body)

    async def remove_tracks_from_playlist(
        self, playlist_id: str, track_uris: List[str],
    ) -> dict:
        """Remove tracks from a playlist."""
        body = {"tracks": [{"uri": uri} for uri in track_uris[:100]]}
        return await self._delete(f"playlists/{playlist_id}/tracks", json_body=body)

    async def reorder_playlist_tracks(
        self,
        playlist_id: str,
        range_start: int,
        insert_before: int,
        range_length: int = 1,
    ) -> dict:
        """Move tracks within a playlist."""
        body = {
            "range_start": range_start,
            "insert_before": insert_before,
            "range_length": range_length,
        }
        return await self._put(f"playlists/{playlist_id}/tracks", json_body=body)

    async def update_playlist_details(
        self,
        playlist_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        public: Optional[bool] = None,
    ) -> dict:
        """Update a playlist's name, description, or visibility."""
        body = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if public is not None:
            body["public"] = public
        return await self._put(f"playlists/{playlist_id}", json_body=body)

    # ===================================================================
    # PLAYER / PLAYBACK CONTROL  (Requires Spotify Premium)
    # ===================================================================

    async def get_playback_state(self, market: str = "US") -> dict:
        """Get the current playback state (device, progress, track, etc.)."""
        raw = await self._get("me/player", market=market)
        if "error" in raw:
            return raw
        if not raw or raw.get("success"):
            return {"is_playing": False, "device": None, "item": None}
        item = raw.get("item")
        device = raw.get("device")
        return {
            "is_playing": raw.get("is_playing"),
            "progress_ms": raw.get("progress_ms"),
            "shuffle_state": raw.get("shuffle_state"),
            "repeat_state": raw.get("repeat_state"),
            "device": _simplify_device(device) if device else None,
            "item": _simplify_track(item) if item else None,
        }

    async def get_currently_playing(self, market: str = "US") -> dict:
        """Get the currently playing track."""
        raw = await self._get("me/player/currently-playing", market=market)
        if "error" in raw:
            return raw
        if not raw or raw.get("success"):
            return {"is_playing": False, "item": None}
        item = raw.get("item")
        return {
            "is_playing": raw.get("is_playing"),
            "progress_ms": raw.get("progress_ms"),
            "item": _simplify_track(item) if item else None,
        }

    async def start_playback(
        self,
        uris: Optional[List[str]] = None,
        context_uri: Optional[str] = None,
        device_id: Optional[str] = None,
        offset: Optional[dict] = None,
        position_ms: int = 0,
    ) -> dict:
        """
        Start or resume playback.

        Args:
            uris:         List of Spotify track URIs to play.
            context_uri:  Spotify URI of a context (album, playlist, artist).
            device_id:    Target device. If omitted, uses the active device.
            offset:       Where in the context to start, e.g. ``{"position": 0}``
                          or ``{"uri": "spotify:track:..."}``.
            position_ms:  Position in ms to seek to within the track.
        """
        body: Dict[str, Any] = {}
        if uris:
            body["uris"] = uris
        if context_uri:
            body["context_uri"] = context_uri
        if offset:
            body["offset"] = offset
        if position_ms:
            body["position_ms"] = position_ms

        params = {}
        if device_id:
            params["device_id"] = device_id
        return await self._put("me/player/play", json_body=body, **params)

    async def pause_playback(self, device_id: Optional[str] = None) -> dict:
        """Pause playback."""
        params = {}
        if device_id:
            params["device_id"] = device_id
        return await self._put("me/player/pause", **params)

    async def skip_to_next(self, device_id: Optional[str] = None) -> dict:
        """Skip to the next track."""
        params = {}
        if device_id:
            params["device_id"] = device_id
        return await self._post("me/player/next", **params)

    async def skip_to_previous(self, device_id: Optional[str] = None) -> dict:
        """Skip to the previous track."""
        params = {}
        if device_id:
            params["device_id"] = device_id
        return await self._post("me/player/previous", **params)

    async def seek_to_position(
        self, position_ms: int, device_id: Optional[str] = None,
    ) -> dict:
        """Seek to a position in the currently playing track."""
        params = {"position_ms": position_ms}
        if device_id:
            params["device_id"] = device_id
        return await self._put("me/player/seek", **params)

    async def set_volume(
        self, volume_percent: int, device_id: Optional[str] = None,
    ) -> dict:
        """Set playback volume (0-100)."""
        params = {"volume_percent": max(0, min(100, volume_percent))}
        if device_id:
            params["device_id"] = device_id
        return await self._put("me/player/volume", **params)

    async def set_repeat_mode(
        self, state: str = "off", device_id: Optional[str] = None,
    ) -> dict:
        """
        Set repeat mode.

        Args:
            state: ``track``, ``context``, or ``off``.
        """
        params = {"state": state}
        if device_id:
            params["device_id"] = device_id
        return await self._put("me/player/repeat", **params)

    async def toggle_shuffle(
        self, state: bool = True, device_id: Optional[str] = None,
    ) -> dict:
        """Toggle shuffle mode."""
        params = {"state": str(state).lower()}
        if device_id:
            params["device_id"] = device_id
        return await self._put("me/player/shuffle", **params)

    async def get_available_devices(self) -> list:
        """List the user's available Spotify Connect devices."""
        raw = await self._get("me/player/devices")
        if "error" in raw:
            return raw
        return [_simplify_device(d) for d in raw.get("devices", [])]

    async def transfer_playback(self, device_id: str, play: bool = True) -> dict:
        """Transfer playback to a different device."""
        return await self._put(
            "me/player", json_body={"device_ids": [device_id], "play": play},
        )

    async def get_queue(self) -> dict:
        """Get the user's current playback queue."""
        raw = await self._get("me/player/queue")
        if "error" in raw:
            return raw
        currently = raw.get("currently_playing")
        return {
            "currently_playing": _simplify_track(currently) if currently else None,
            "queue": [_simplify_track(t) for t in raw.get("queue", [])],
        }

    async def add_to_queue(self, uri: str, device_id: Optional[str] = None) -> dict:
        """Add a track to the end of the user's playback queue."""
        params = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        return await self._post("me/player/queue", **params)

    # ===================================================================
    # USER LIBRARY (Saved / Liked)
    # ===================================================================

    async def get_user_saved_tracks(
        self, limit: int = 20, offset: int = 0, market: str = "US",
    ) -> dict:
        """Get the user's liked songs."""
        raw = await self._get("me/tracks", limit=limit, offset=offset, market=market)
        if "error" in raw:
            return raw
        return {
            "items": [
                _simplify_track(item.get("track", {}))
                for item in raw.get("items", [])
            ],
            "total": raw.get("total"),
            "next": raw.get("next"),
        }

    async def save_tracks(self, track_ids: List[str]) -> dict:
        """Like / save tracks to the user's library."""
        return await self._put("me/tracks", json_body={"ids": track_ids[:50]})

    async def remove_saved_tracks(self, track_ids: List[str]) -> dict:
        """Unlike / remove tracks from the user's library."""
        return await self._delete("me/tracks", json_body={"ids": track_ids[:50]})

    async def check_saved_tracks(self, track_ids: List[str]) -> dict:
        """Check whether tracks are in the user's library."""
        raw = await self._get("me/tracks/contains", ids=",".join(track_ids[:50]))
        if isinstance(raw, list):
            return {tid: saved for tid, saved in zip(track_ids, raw)}
        return raw  # error dict

    async def get_user_saved_albums(
        self, limit: int = 20, offset: int = 0, market: str = "US",
    ) -> dict:
        """Get the user's saved albums."""
        raw = await self._get("me/albums", limit=limit, offset=offset, market=market)
        if "error" in raw:
            return raw
        return {
            "items": [
                _simplify_album(item.get("album", {}))
                for item in raw.get("items", [])
            ],
            "total": raw.get("total"),
            "next": raw.get("next"),
        }

    async def save_albums(self, album_ids: List[str]) -> dict:
        """Save albums to the user's library."""
        return await self._put("me/albums", json_body={"ids": album_ids[:50]})

    async def remove_saved_albums(self, album_ids: List[str]) -> dict:
        """Remove albums from the user's library."""
        return await self._delete("me/albums", json_body={"ids": album_ids[:50]})

    # ===================================================================
    # USER TOP ITEMS & RECENTLY PLAYED
    # ===================================================================

    async def get_user_top_items(
        self,
        item_type: str = "tracks",
        time_range: str = "medium_term",
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """
        Get the user's top tracks or artists.

        Args:
            item_type:   ``tracks`` or ``artists``.
            time_range:  ``short_term`` (~4 weeks), ``medium_term``
                         (~6 months), ``long_term`` (all time).
            limit:       1-50 results.
        """
        raw = await self._get(
            f"me/top/{item_type}",
            time_range=time_range, limit=limit, offset=offset,
        )
        if "error" in raw:
            return raw
        fn = _simplify_track if item_type == "tracks" else _simplify_artist
        return {
            "items": [fn(item) for item in raw.get("items", [])],
            "total": raw.get("total"),
            "next": raw.get("next"),
        }

    async def get_recently_played(self, limit: int = 20) -> list:
        """Get the user's recently played tracks."""
        raw = await self._get("me/player/recently-played", limit=limit)
        if "error" in raw:
            return raw
        return [
            {
                "played_at": item.get("played_at"),
                "track": _simplify_track(item.get("track", {})),
            }
            for item in raw.get("items", [])
        ]

    # ===================================================================
    # RECOMMENDATIONS
    # ===================================================================

    async def get_recommendations(
        self,
        seed_artists: Optional[List[str]] = None,
        seed_genres: Optional[List[str]] = None,
        seed_tracks: Optional[List[str]] = None,
        limit: int = 20,
        market: str = "US",
        **tunable_attributes,
    ) -> dict:
        """
        Get track recommendations.

        You must supply at least one seed (artists, genres, or tracks).
        Up to 5 seeds total across all three types.

        Tunable attributes (pass as kwargs):
            min_energy, max_energy, target_energy,
            min_danceability, max_danceability, target_danceability,
            min_tempo, max_tempo, target_tempo,
            min_valence, max_valence, target_valence,
            min_popularity, max_popularity, target_popularity,
            etc.  See Spotify docs for the full list.

        Returns:
            Dict with ``tracks`` (list of simplified track dicts) and
            ``seeds`` (the seeds used).
        """
        params: Dict[str, Any] = {"limit": limit, "market": market}

        if seed_artists:
            params["seed_artists"] = ",".join(seed_artists[:5])
        if seed_genres:
            params["seed_genres"] = ",".join(seed_genres[:5])
        if seed_tracks:
            params["seed_tracks"] = ",".join(seed_tracks[:5])

        # Merge tunable attributes directly into params
        params.update(tunable_attributes)

        raw = await self._get("recommendations", **params)
        if "error" in raw:
            return raw
        return {
            "tracks": [_simplify_track(t) for t in raw.get("tracks", [])],
            "seeds": raw.get("seeds", []),
        }

    async def get_available_genre_seeds(self) -> list:
        """Get the list of available genre seeds for recommendations."""
        raw = await self._get("recommendations/available-genre-seeds")
        if "error" in raw:
            return raw
        return raw.get("genres", [])

    # ===================================================================
    # USER PROFILE
    # ===================================================================

    async def get_current_user_profile(self) -> dict:
        """Get the authenticated user's profile."""
        raw = await self._get("me")
        if "error" in raw:
            return raw
        return {
            "id": raw.get("id"),
            "display_name": raw.get("display_name"),
            "email": raw.get("email"),
            "country": raw.get("country"),
            "product": raw.get("product"),  # "premium", "free", etc.
            "followers": raw.get("followers", {}).get("total"),
            "images": raw.get("images", [])[:1],
            "uri": raw.get("uri"),
        }

    async def get_user_profile(self, user_id: str) -> dict:
        """Get a user's public profile."""
        raw = await self._get(f"users/{user_id}")
        if "error" in raw:
            return raw
        return {
            "id": raw.get("id"),
            "display_name": raw.get("display_name"),
            "followers": raw.get("followers", {}).get("total"),
            "images": raw.get("images", [])[:1],
            "uri": raw.get("uri"),
        }

    # ===================================================================
    # FOLLOW
    # ===================================================================

    async def follow_artists_or_users(
        self, ids: List[str], follow_type: str = "artist",
    ) -> dict:
        """Follow artists or users."""
        return await self._put(
            "me/following", json_body={"ids": ids[:50]}, type=follow_type,
        )

    async def unfollow_artists_or_users(
        self, ids: List[str], follow_type: str = "artist",
    ) -> dict:
        """Unfollow artists or users."""
        return await self._delete(
            "me/following", json_body={"ids": ids[:50]}, type=follow_type,
        )

    async def check_following(
        self, ids: List[str], follow_type: str = "artist",
    ) -> dict:
        """Check if the user follows specific artists/users."""
        raw = await self._get(
            "me/following/contains", type=follow_type, ids=",".join(ids[:50]),
        )
        if isinstance(raw, list):
            return {fid: following for fid, following in zip(ids, raw)}
        return raw

    async def get_followed_artists(self, limit: int = 20, after: Optional[str] = None) -> dict:
        """Get the user's followed artists (cursor-based pagination)."""
        params = {"type": "artist", "limit": limit}
        if after:
            params["after"] = after
        raw = await self._get("me/following", **params)
        if "error" in raw:
            return raw
        artists_section = raw.get("artists", {})
        return {
            "items": [_simplify_artist(a) for a in artists_section.get("items", [])],
            "total": artists_section.get("total"),
            "cursor_after": (artists_section.get("cursors") or {}).get("after"),
        }

    # ===================================================================
    # SHOWS & EPISODES (Podcasts)
    # ===================================================================

    async def get_show(self, show_id: str, market: str = "US") -> dict:
        """Get a podcast show's details."""
        return await self._get(f"shows/{show_id}", market=market)

    async def get_show_episodes(
        self, show_id: str, limit: int = 20, offset: int = 0, market: str = "US",
    ) -> dict:
        """Get episodes of a podcast show."""
        return await self._get(
            f"shows/{show_id}/episodes", limit=limit, offset=offset, market=market,
        )

    async def get_episode(self, episode_id: str, market: str = "US") -> dict:
        """Get a podcast episode's details."""
        return await self._get(f"episodes/{episode_id}", market=market)

    async def get_user_saved_shows(self, limit: int = 20, offset: int = 0) -> dict:
        """Get the user's saved podcast shows."""
        return await self._get("me/shows", limit=limit, offset=offset)

    async def save_shows(self, show_ids: List[str]) -> dict:
        """Save podcast shows to the user's library."""
        return await self._put("me/shows", ids=",".join(show_ids[:50]))

    async def remove_saved_shows(self, show_ids: List[str]) -> dict:
        """Remove saved podcast shows."""
        return await self._delete("me/shows", ids=",".join(show_ids[:50]))

    # ===================================================================
    # NEW RELEASES & FEATURED PLAYLISTS (Browse)
    # ===================================================================

    async def get_new_releases(
        self, country: str = "US", limit: int = 20, offset: int = 0,
    ) -> dict:
        """Get new album releases."""
        raw = await self._get(
            "browse/new-releases", country=country, limit=limit, offset=offset,
        )
        if "error" in raw:
            return raw
        albums_section = raw.get("albums", {})
        return {
            "items": [_simplify_album(a) for a in albums_section.get("items", [])],
            "total": albums_section.get("total"),
            "next": albums_section.get("next"),
        }

    async def get_featured_playlists(
        self, country: str = "US", limit: int = 20, offset: int = 0,
    ) -> dict:
        """Get Spotify's featured playlists."""
        raw = await self._get(
            "browse/featured-playlists", country=country, limit=limit, offset=offset,
        )
        if "error" in raw:
            return raw
        pl_section = raw.get("playlists", {})
        return {
            "message": raw.get("message"),
            "items": [_simplify_playlist(p) for p in pl_section.get("items", [])],
            "total": pl_section.get("total"),
        }

    async def get_categories(
        self, country: str = "US", limit: int = 20, offset: int = 0,
    ) -> dict:
        """Get Spotify browse categories."""
        raw = await self._get(
            "browse/categories", country=country, limit=limit, offset=offset,
        )
        if "error" in raw:
            return raw
        cat_section = raw.get("categories", {})
        return {
            "items": [
                {"id": c.get("id"), "name": c.get("name"), "icons": c.get("icons", [])[:1]}
                for c in cat_section.get("items", [])
            ],
            "total": cat_section.get("total"),
        }

    async def get_category_playlists(
        self, category_id: str, country: str = "US", limit: int = 20, offset: int = 0,
    ) -> dict:
        """Get playlists tagged with a specific category."""
        raw = await self._get(
            f"browse/categories/{category_id}/playlists",
            country=country, limit=limit, offset=offset,
        )
        if "error" in raw:
            return raw
        pl_section = raw.get("playlists", {})
        return {
            "items": [_simplify_playlist(p) for p in pl_section.get("items", [])],
            "total": pl_section.get("total"),
        }


# ---------------------------------------------------------------------------
# Singleton instance — import and use: ``from arcis.core.external_api.spotify import spotify_api``
# ---------------------------------------------------------------------------
spotify_api = SpotifyAPI()
