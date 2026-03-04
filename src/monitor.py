import logging
import time

from src.database import (
    get_active_playlists,
    get_known_track_ids,
    is_first_run,
    save_tracks,
    update_snapshot_id,
)
from src.lyrics import get_lyrics
from src.groq_client import analyze_track
from src.spotify import SpotifyClient
from src.telegram import (
    send_analysis_notification,
    send_error_notification,
    send_new_track_notification,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)

logger = logging.getLogger(__name__)


def _check_playlist(client: SpotifyClient, playlist: dict) -> None:
    playlist_id = playlist["id"]
    playlist_name = playlist["name"]

    if is_first_run(playlist_id):
        # Full scan to build the baseline — no notifications sent.
        # Fetch snapshot_id upfront so we can store it after the baseline.
        info = client.get_playlist_info(playlist_id)
        if info is None:
            logger.warning(
                "Could not fetch playlist info for '%s' (%s) — skipping.",
                playlist_name,
                playlist_id,
            )
            return
        all_tracks = client.get_playlist_tracks(playlist_id)
        if not all_tracks:
            logger.warning(
                "Playlist '%s' (%s) returned no tracks — private or inaccessible, skipping.",
                playlist_name,
                playlist_id,
            )
            return
        save_tracks(all_tracks, playlist_id)
        update_snapshot_id(playlist_id, info["snapshot_id"])
        logger.info(
            "First run for '%s': saved %d tracks, no notifications sent.",
            playlist_name,
            len(all_tracks),
        )
        return

    # Use the Spotify API snapshot_id as an authoritative change gate.
    # snapshot_id changes on any playlist modification; if it matches what
    # we stored last run, nothing has changed — skip Playwright entirely.
    info = client.get_playlist_info(playlist_id)
    if info is None:
        logger.warning(
            "Could not fetch playlist info for '%s' (%s) — skipping.",
            playlist_name,
            playlist_id,
        )
        return

    api_snapshot = info["snapshot_id"]
    stored_snapshot = playlist["snapshot_id"]  # None if never set

    if api_snapshot == stored_snapshot:
        logger.info("No changes in '%s' (snapshot unchanged).", playlist_name)
        return

    logger.info(
        "Playlist '%s' changed (snapshot updated) — scraping.",
        playlist_name,
    )

    # Incremental scan: jump to the end, scroll up until a known track is
    # found. Returns only tracks added since the last run.
    known_ids = get_known_track_ids(playlist_id)
    new_tracks = client.get_playlist_tracks(playlist_id, known_ids=known_ids)

    if not new_tracks:
        logger.info("No new tracks scraped from '%s'.", playlist_name)
        update_snapshot_id(playlist_id, api_snapshot)
        return

    logger.info(
        "%d new track(s) detected in '%s'.", len(new_tracks), playlist_name
    )

    for track in new_tracks:
        send_new_track_notification(track, playlist_name)
        time.sleep(1)  # Telegram rate limit: 1 message/second per chat

        try:
            primary_artist = track.artist_names[0] if track.artist_names else ""
            lyrics = get_lyrics(track.track_name, primary_artist)
            analysis = analyze_track(track.track_name, primary_artist, lyrics)
            if analysis:
                send_analysis_notification(analysis)
                time.sleep(1)
        except Exception:
            logger.warning(
                "Analysis failed for '%s' — skipping.", track.track_name, exc_info=True
            )

    save_tracks(new_tracks, playlist_id)
    update_snapshot_id(playlist_id, api_snapshot)


def run() -> None:
    client = SpotifyClient()
    client.authenticate()
    playlists = get_active_playlists()

    if not playlists:
        logger.info("No active playlists to monitor.")
        return

    logger.info("Monitoring %d playlist(s).", len(playlists))

    for playlist in playlists:
        playlist_id = playlist["id"]
        playlist_name = playlist["name"]

        logger.info("Checking playlist: '%s' (%s)", playlist_name, playlist_id)
        try:
            _check_playlist(client, playlist)
        except Exception as exc:
            logger.exception(
                "Error processing playlist '%s' (%s).", playlist_name, playlist_id
            )
            send_error_notification(
                f"Playlist '{playlist_name}' ({playlist_id}) failed: {exc}"
            )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        logger.exception("Unhandled exception in monitor run.")
        send_error_notification(str(exc))
        raise
