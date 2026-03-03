"""
Integration test for database state management.
Tests is_first_run(), get_known_track_ids(), and save_tracks() against a real DB.

Usage: python -m scripts.test_database
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    from src.database import (
        get_active_playlists,
        get_known_track_ids,
        is_first_run,
        save_tracks,
    )
    from src.spotify import SpotifyClient

    playlists = get_active_playlists()
    if not playlists:
        print("No active playlists found. Add one with manage_playlists.py first.")
        sys.exit(1)

    playlist = playlists[0]
    playlist_id = playlist["id"]
    playlist_name = playlist["name"]
    print(f"\nTesting against playlist: '{playlist_name}' ({playlist_id})\n")

    # --- 1. is_first_run() ---
    first_run = is_first_run(playlist_id)
    known_before = get_known_track_ids(playlist_id)
    print(f"[1] is_first_run()        : {first_run}")
    print(f"[1] known track IDs count : {len(known_before)}")

    # --- 2. Fetch tracks from Spotify ---
    client = SpotifyClient()
    client.authenticate()
    tracks = client.get_playlist_tracks(playlist_id)
    print(f"\n[2] Tracks fetched from Spotify: {len(tracks)}")

    # --- 3. save_tracks() ---
    save_tracks(tracks, playlist_id)
    known_after = get_known_track_ids(playlist_id)
    print(f"\n[3] Known track IDs after save : {len(known_after)}")
    assert len(known_after) == len(tracks), "Mismatch between saved and fetched count."

    # --- 4. Duplicate prevention ---
    save_tracks(tracks, playlist_id)
    known_after_duplicate = get_known_track_ids(playlist_id)
    assert len(known_after_duplicate) == len(known_after), "Duplicate tracks were inserted."
    print(f"[4] After duplicate save_tracks: {len(known_after_duplicate)} (no duplicates)")

    # --- 5. is_first_run() should now be False ---
    assert not is_first_run(playlist_id), "is_first_run() should return False after saving."
    print(f"[5] is_first_run() after save  : {is_first_run(playlist_id)}")

    print("\nIssue 3 Definition of Done: PASSED")


if __name__ == "__main__":
    main()
