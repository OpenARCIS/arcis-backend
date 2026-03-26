import json
from typing import Optional
from langchain.tools import tool

from arcis.core.external_api.spotify import spotify_api
from arcis.logger import LOGGER


def _format_result(data: dict | list) -> str:
    """Compact JSON output for LLM consumption."""
    return json.dumps(data, indent=2, default=str)


# ===================================================================
# SEARCH
# ===================================================================

@tool
async def spotify_search(query: str, types: str = "track", limit: int = 5) -> str:
    """
    Search the Spotify catalogue for tracks, albums, artists, or playlists.
    Use this as the starting point when the user mentions a song, artist, or album by name.

    Args:
        query: Free-text search (e.g. 'Bohemian Rhapsody', 'Taylor Swift', 'chill vibes playlist').
        types: Comma-separated item types: track, album, artist, playlist, show, episode.
        limit: Number of results per type (1-50, default 5).
    """
    try:
        result = await spotify_api.search(query, types=types, limit=limit)
        if "error" in result:
            return f"❌ Search failed: {result['error']}"
        return f"🔍 Search results for '{query}':\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Search error: {e}"


# ===================================================================
# TRACK INFO
# ===================================================================

@tool
async def spotify_get_track(track_id: str) -> str:
    """
    Get details of a specific track by its Spotify ID.

    Args:
        track_id: The Spotify track ID (e.g. '11dFghVXANMlKmJXsNCbNl').
    """
    try:
        result = await spotify_api.get_track(track_id)
        if "error" in result:
            return f"❌ Failed to get track: {result['error']}"
        return f"🎵 Track info:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_audio_features(track_id: str) -> str:
    """
    Get audio analysis features for a track: tempo, energy, danceability, valence, etc.
    Useful for understanding the mood/characteristics of a song or building smart playlists.

    Args:
        track_id: The Spotify track ID.
    """
    try:
        result = await spotify_api.get_audio_features(track_id)
        if "error" in result:
            return f"❌ Failed to get audio features: {result['error']}"
        return f"🎛️ Audio features for {track_id}:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# ALBUM INFO
# ===================================================================

@tool
async def spotify_get_album(album_id: str) -> str:
    """
    Get album details and its track listing.

    Args:
        album_id: The Spotify album ID.
    """
    try:
        result = await spotify_api.get_album(album_id)
        if "error" in result:
            return f"❌ Failed to get album: {result['error']}"
        return f"💿 Album info:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# ARTIST INFO
# ===================================================================

@tool
async def spotify_get_artist(artist_id: str) -> str:
    """
    Get artist details including genres, popularity, and follower count.

    Args:
        artist_id: The Spotify artist ID.
    """
    try:
        result = await spotify_api.get_artist(artist_id)
        if "error" in result:
            return f"❌ Failed to get artist: {result['error']}"
        return f"🎤 Artist info:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_artist_top_tracks(artist_id: str) -> str:
    """
    Get an artist's most popular tracks. Useful when the user wants to hear
    an artist's best songs or discover their hits.

    Args:
        artist_id: The Spotify artist ID.
    """
    try:
        result = await spotify_api.get_artist_top_tracks(artist_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🔥 Top tracks:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_related_artists(artist_id: str) -> str:
    """
    Find artists similar to a given artist. Good for music discovery
    and building varied playlists.

    Args:
        artist_id: The Spotify artist ID.
    """
    try:
        result = await spotify_api.get_related_artists(artist_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎶 Related artists:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# PLAYBACK CONTROL (Premium required)
# ===================================================================

@tool
async def spotify_get_playback_state() -> str:
    """
    Get current playback state: what's playing, on which device, progress,
    shuffle/repeat status. Call this to understand what the user is
    currently listening to before making playback changes.
    """
    try:
        result = await spotify_api.get_playback_state()
        if "error" in result:
            return f"❌ Playback state error: {result['error']}"
        if not result.get("is_playing") and not result.get("device"):
            return "⏹️ Nothing is currently playing and no active device found."
        return f"▶️ Playback state:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_play(
    track_uris: Optional[str] = None,
    context_uri: Optional[str] = None,
    device_id: Optional[str] = None,
) -> str:
    """
    Start or resume playback. Can play specific tracks or a context (album/playlist/artist).
    Requires Spotify Premium and an active device.

    Args:
        track_uris: Comma-separated Spotify track URIs to play (e.g. 'spotify:track:abc,spotify:track:def'). Leave empty to resume paused playback.
        context_uri: A Spotify context URI to play (album, playlist, or artist). e.g. 'spotify:album:abc' or 'spotify:playlist:xyz'.
        device_id: Target device ID. If omitted, uses the currently active device. Use spotify_get_devices to list devices.
    """
    try:
        uris = [u.strip() for u in track_uris.split(",")] if track_uris else None
        result = await spotify_api.start_playback(
            uris=uris, context_uri=context_uri, device_id=device_id,
        )
        if "error" in result:
            return f"❌ Playback failed: {result['error']} (Requires Premium & active device)"
        return "▶️ Playback started."
    except Exception as e:
        return f"❌ Error starting playback: {e}"


@tool
async def spotify_pause(device_id: Optional[str] = None) -> str:
    """
    Pause the current playback. Requires Spotify Premium.

    Args:
        device_id: Target device ID. If omitted, pauses the active device.
    """
    try:
        result = await spotify_api.pause_playback(device_id)
        if "error" in result:
            return f"❌ Pause failed: {result['error']}"
        return "⏸️ Playback paused."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_skip_next(device_id: Optional[str] = None) -> str:
    """
    Skip to the next track in the queue. Requires Spotify Premium.

    Args:
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.skip_to_next(device_id)
        if "error" in result:
            return f"❌ Skip failed: {result['error']}"
        return "⏭️ Skipped to next track."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_skip_previous(device_id: Optional[str] = None) -> str:
    """
    Skip to the previous track. Requires Spotify Premium.

    Args:
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.skip_to_previous(device_id)
        if "error" in result:
            return f"❌ Skip failed: {result['error']}"
        return "⏮️ Skipped to previous track."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_set_volume(volume_percent: int, device_id: Optional[str] = None) -> str:
    """
    Set playback volume. Requires Spotify Premium.

    Args:
        volume_percent: Volume level from 0 to 100.
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.set_volume(volume_percent, device_id)
        if "error" in result:
            return f"❌ Volume change failed: {result['error']}"
        return f"🔊 Volume set to {volume_percent}%."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_seek(position_ms: int, device_id: Optional[str] = None) -> str:
    """
    Seek to a position in the currently playing track.

    Args:
        position_ms: Position in milliseconds to seek to.
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.seek_to_position(position_ms, device_id)
        if "error" in result:
            return f"❌ Seek failed: {result['error']}"
        secs = position_ms // 1000
        return f"⏩ Seeked to {secs // 60}:{secs % 60:02d}."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_set_repeat(state: str = "off", device_id: Optional[str] = None) -> str:
    """
    Set repeat mode for playback.

    Args:
        state: One of 'track' (repeat current track), 'context' (repeat album/playlist), or 'off'.
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.set_repeat_mode(state, device_id)
        if "error" in result:
            return f"❌ Repeat mode failed: {result['error']}"
        return f"🔁 Repeat mode set to '{state}'."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_set_shuffle(enabled: bool = True, device_id: Optional[str] = None) -> str:
    """
    Toggle shuffle mode on or off.

    Args:
        enabled: True to enable shuffle, False to disable.
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.toggle_shuffle(enabled, device_id)
        if "error" in result:
            return f"❌ Shuffle toggle failed: {result['error']}"
        return f"🔀 Shuffle {'enabled' if enabled else 'disabled'}."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_devices() -> str:
    """
    List all available Spotify Connect devices (phone, desktop, speaker, etc.).
    Use this to find a device_id before transferring or starting playback.
    """
    try:
        result = await spotify_api.get_available_devices()
        if isinstance(result, dict) and "error" in result:
            return f"❌ Failed to list devices: {result['error']}"
        if not result:
            return "📱 No active Spotify devices found. Open Spotify on a device first."
        return f"📱 Available devices:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_transfer_playback(device_id: str, play: bool = True) -> str:
    """
    Transfer playback to a different device.

    Args:
        device_id: The ID of the device to transfer to (get from spotify_get_devices).
        play: If True, start playing on the new device. If False, keep paused state.
    """
    try:
        result = await spotify_api.transfer_playback(device_id, play)
        if "error" in result:
            return f"❌ Transfer failed: {result['error']}"
        return f"📲 Playback transferred to device {device_id}."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_queue() -> str:
    """
    Get the current playback queue: what's playing now and what's coming next.
    """
    try:
        result = await spotify_api.get_queue()
        if "error" in result:
            return f"❌ Queue error: {result['error']}"
        return f"📋 Current queue:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_add_to_queue(uri: str, device_id: Optional[str] = None) -> str:
    """
    Add a track to the end of the playback queue.

    Args:
        uri: Spotify URI of the track to add (e.g. 'spotify:track:4iV5W9uYEdYUVa79Axb7Rh').
        device_id: Target device ID (optional).
    """
    try:
        result = await spotify_api.add_to_queue(uri, device_id)
        if "error" in result:
            return f"❌ Add to queue failed: {result['error']}"
        return f"➕ Added to queue: {uri}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# PLAYLISTS
# ===================================================================

@tool
async def spotify_get_my_playlists(limit: int = 20) -> str:
    """
    Get the user's own playlists. Use this to see what playlists
    the user has before adding/removing tracks.

    Args:
        limit: Number of playlists to return (1-50, default 20).
    """
    try:
        result = await spotify_api.get_current_user_playlists(limit=limit)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📂 Your playlists:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_playlist(playlist_id: str) -> str:
    """
    Get a playlist's details and track listing by its ID.

    Args:
        playlist_id: The Spotify playlist ID.
    """
    try:
        result = await spotify_api.get_playlist(playlist_id)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📂 Playlist info:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_create_playlist(name: str, description: str = "", public: bool = True) -> str:
    """
    Create a new playlist for the user.

    Args:
        name: Name of the playlist.
        description: Optional description.
        public: Whether the playlist is public (default True).
    """
    try:
        result = await spotify_api.create_playlist(name, description, public)
        if "error" in result:
            return f"❌ Failed to create playlist: {result['error']}"
        return f"✅ Playlist created:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_add_tracks_to_playlist(playlist_id: str, track_uris: str) -> str:
    """
    Add tracks to an existing playlist.

    Args:
        playlist_id: The Spotify playlist ID.
        track_uris: Comma-separated Spotify track URIs (e.g. 'spotify:track:abc,spotify:track:def').
    """
    try:
        uris = [u.strip() for u in track_uris.split(",")]
        result = await spotify_api.add_tracks_to_playlist(playlist_id, uris)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"✅ Added {len(uris)} track(s) to playlist {playlist_id}."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_remove_tracks_from_playlist(playlist_id: str, track_uris: str) -> str:
    """
    Remove tracks from a playlist.

    Args:
        playlist_id: The Spotify playlist ID.
        track_uris: Comma-separated Spotify track URIs to remove.
    """
    try:
        uris = [u.strip() for u in track_uris.split(",")]
        result = await spotify_api.remove_tracks_from_playlist(playlist_id, uris)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"✅ Removed {len(uris)} track(s) from playlist {playlist_id}."
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# USER LIBRARY (Liked Songs)
# ===================================================================

@tool
async def spotify_get_liked_songs(limit: int = 20, offset: int = 0) -> str:
    """
    Get the user's liked/saved songs.

    Args:
        limit: Number of tracks to return (1-50, default 20).
        offset: Pagination offset (default 0).
    """
    try:
        result = await spotify_api.get_user_saved_tracks(limit=limit, offset=offset)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"❤️ Liked songs (showing {len(result.get('items', []))} of {result.get('total', '?')}):\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_like_tracks(track_ids: str) -> str:
    """
    Like/save tracks to the user's library.

    Args:
        track_ids: Comma-separated Spotify track IDs to like.
    """
    try:
        ids = [i.strip() for i in track_ids.split(",")]
        result = await spotify_api.save_tracks(ids)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"❤️ Liked {len(ids)} track(s)."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_unlike_tracks(track_ids: str) -> str:
    """
    Remove tracks from the user's liked songs.

    Args:
        track_ids: Comma-separated Spotify track IDs to unlike.
    """
    try:
        ids = [i.strip() for i in track_ids.split(",")]
        result = await spotify_api.remove_saved_tracks(ids)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"💔 Unliked {len(ids)} track(s)."
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# RECOMMENDATIONS & DISCOVERY
# ===================================================================

@tool
async def spotify_get_recommendations(
    seed_artists: Optional[str] = None,
    seed_genres: Optional[str] = None,
    seed_tracks: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Get personalized track recommendations based on seed artists, genres, or tracks.
    At least one seed is required. Up to 5 seeds total across all types.
    Great for discovering new music or building playlists around a mood.

    Args:
        seed_artists: Comma-separated artist IDs (e.g. '4NHQUGzhtTLFvgF5SZesLK').
        seed_genres: Comma-separated genre names (e.g. 'pop,indie,electronic'). Use spotify_get_genre_seeds for valid genres.
        seed_tracks: Comma-separated track IDs.
        limit: Number of recommendations (1-100, default 10).
    """
    try:
        artists = [a.strip() for a in seed_artists.split(",")] if seed_artists else None
        genres = [g.strip() for g in seed_genres.split(",")] if seed_genres else None
        tracks = [t.strip() for t in seed_tracks.split(",")] if seed_tracks else None

        result = await spotify_api.get_recommendations(
            seed_artists=artists, seed_genres=genres, seed_tracks=tracks, limit=limit,
        )
        if "error" in result:
            return f"❌ Recommendation failed: {result['error']}"
        return f"🎧 Recommendations ({len(result.get('tracks', []))} tracks):\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_genre_seeds() -> str:
    """
    Get the full list of available genre seeds for recommendations.
    Call this before using spotify_get_recommendations with genre seeds
    to ensure valid genre names.
    """
    try:
        result = await spotify_api.get_available_genre_seeds()
        if isinstance(result, dict) and "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎼 Available genres ({len(result)}):\n{', '.join(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# USER PROFILE & LISTENING HISTORY
# ===================================================================

@tool
async def spotify_get_my_profile() -> str:
    """
    Get the authenticated user's Spotify profile: display name, email,
    subscription type (free/premium), country, etc.
    """
    try:
        result = await spotify_api.get_current_user_profile()
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"👤 Your profile:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_top_items(
    item_type: str = "tracks",
    time_range: str = "medium_term",
    limit: int = 10,
) -> str:
    """
    Get the user's top tracks or artists based on listening history.

    Args:
        item_type: 'tracks' or 'artists'.
        time_range: 'short_term' (~4 weeks), 'medium_term' (~6 months), 'long_term' (all time).
        limit: Number of results (1-50, default 10).
    """
    try:
        result = await spotify_api.get_user_top_items(
            item_type=item_type, time_range=time_range, limit=limit,
        )
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"📊 Your top {item_type} ({time_range}):\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_recently_played(limit: int = 10) -> str:
    """
    Get the user's recently played tracks.

    Args:
        limit: Number of recent tracks to return (1-50, default 10).
    """
    try:
        result = await spotify_api.get_recently_played(limit=limit)
        if isinstance(result, dict) and "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🕐 Recently played ({len(result)} tracks):\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_currently_playing() -> str:
    """
    Get the track that is currently playing right now.
    Lighter than spotify_get_playback_state — just the track and play status.
    """
    try:
        result = await spotify_api.get_currently_playing()
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        if not result.get("is_playing"):
            return "⏹️ Nothing is currently playing."
        return f"🎵 Now playing:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# BROWSE & DISCOVERY
# ===================================================================

@tool
async def spotify_get_new_releases(limit: int = 10) -> str:
    """
    Get new album releases on Spotify. Good for discovering fresh music.

    Args:
        limit: Number of releases (1-50, default 10).
    """
    try:
        result = await spotify_api.get_new_releases(limit=limit)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🆕 New releases:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_featured_playlists(limit: int = 10) -> str:
    """
    Get Spotify's currently featured/editorial playlists.
    Good for mood-based or activity-based listening.

    Args:
        limit: Number of playlists (1-50, default 10).
    """
    try:
        result = await spotify_api.get_featured_playlists(limit=limit)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"⭐ Featured playlists:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# FOLLOW
# ===================================================================

@tool
async def spotify_follow_artist(artist_id: str) -> str:
    """
    Follow an artist on Spotify.

    Args:
        artist_id: The Spotify artist ID to follow.
    """
    try:
        result = await spotify_api.follow_artists_or_users([artist_id], follow_type="artist")
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"✅ Now following artist {artist_id}."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_unfollow_artist(artist_id: str) -> str:
    """
    Unfollow an artist on Spotify.

    Args:
        artist_id: The Spotify artist ID to unfollow.
    """
    try:
        result = await spotify_api.unfollow_artists_or_users([artist_id], follow_type="artist")
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"✅ Unfollowed artist {artist_id}."
    except Exception as e:
        return f"❌ Error: {e}"


@tool
async def spotify_get_followed_artists(limit: int = 20) -> str:
    """
    Get the list of artists the user follows.

    Args:
        limit: Number of artists to return (1-50, default 20).
    """
    try:
        result = await spotify_api.get_followed_artists(limit=limit)
        if "error" in result:
            return f"❌ Failed: {result['error']}"
        return f"🎤 Followed artists:\n{_format_result(result)}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===================================================================
# EXPORT: All tools grouped for easy registration
# ===================================================================

spotify_tools = [
    # Search & Info
    spotify_search,
    spotify_get_track,
    spotify_get_audio_features,
    spotify_get_album,
    spotify_get_artist,
    spotify_get_artist_top_tracks,
    spotify_get_related_artists,
    # Playback Control
    spotify_get_playback_state,
    spotify_get_currently_playing,
    spotify_play,
    spotify_pause,
    spotify_skip_next,
    spotify_skip_previous,
    spotify_set_volume,
    spotify_seek,
    spotify_set_repeat,
    spotify_set_shuffle,
    spotify_get_devices,
    spotify_transfer_playback,
    spotify_get_queue,
    spotify_add_to_queue,
    # Playlists
    spotify_get_my_playlists,
    spotify_get_playlist,
    spotify_create_playlist,
    spotify_add_tracks_to_playlist,
    spotify_remove_tracks_from_playlist,
    # Library
    spotify_get_liked_songs,
    spotify_like_tracks,
    spotify_unlike_tracks,
    # Recommendations & Discovery
    spotify_get_recommendations,
    spotify_get_genre_seeds,
    spotify_get_new_releases,
    spotify_get_featured_playlists,
    # User
    spotify_get_my_profile,
    spotify_get_top_items,
    spotify_get_recently_played,
    # Follow
    spotify_follow_artist,
    spotify_unfollow_artist,
    spotify_get_followed_artists,
]
