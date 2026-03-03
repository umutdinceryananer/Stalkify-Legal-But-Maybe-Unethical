import logging
import time

from src.database import (
    get_active_playlists,
    get_known_track_count,
    get_known_track_ids,
    is_first_run,
    save_tracks,
)
from src.spotify import SpotifyClient
from src.telegram import send_error_notification, send_new_track_notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)

logger = logging.getLogger(__name__)


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

        if is_first_run(playlist_id):
            # Full scan to build the baseline — no notifications sent.
            all_tracks = client.get_playlist_tracks(playlist_id)
            if not all_tracks:
                logger.warning(
                    "Playlist '%s' (%s) returned no tracks — private or inaccessible, skipping.",
                    playlist_name,
                    playlist_id,
                )
                continue
            save_tracks(all_tracks, playlist_id)
            logger.info(
                "First run for '%s': saved %d tracks, no notifications sent.",
                playlist_name,
                len(all_tracks),
            )
            continue

        # Use the Spotify API track count as an authoritative gate.
        # Only launch Playwright if the API confirms new tracks were added.
        info = client.get_playlist_info(playlist_id)
        if info is None:
            logger.warning(
                "Could not fetch playlist info for '%s' (%s) — skipping.",
                playlist_name,
                playlist_id,
            )
            continue

        api_count = info["track_count"]
        db_count = get_known_track_count(playlist_id)
        expected_new = api_count - db_count

        if expected_new <= 0:
            logger.info(
                "No new tracks in '%s' (API: %d, DB: %d).",
                playlist_name,
                api_count,
                db_count,
            )
            continue

        logger.info(
            "%d new track(s) expected in '%s' (API: %d, DB: %d) — scraping.",
            expected_new,
            playlist_name,
            api_count,
            db_count,
        )

        # Incremental scan: jump to the end, scroll up until a known track is
        # found or exactly expected_new tracks have been collected.
        known_ids = get_known_track_ids(playlist_id)
        new_tracks = client.get_playlist_tracks(
            playlist_id, known_ids=known_ids, expected_new=expected_new
        )

        if not new_tracks:
            logger.info("No new tracks scraped from '%s'.", playlist_name)
            continue

        logger.info(
            "%d new track(s) detected in '%s'.", len(new_tracks), playlist_name
        )

        for track in new_tracks:
            send_new_track_notification(track, playlist_name)
            time.sleep(1)  # Telegram rate limit: 1 message/second per chat

        save_tracks(new_tracks, playlist_id)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        logger.exception("Unhandled exception in monitor run.")
        send_error_notification(str(exc))
        raise
