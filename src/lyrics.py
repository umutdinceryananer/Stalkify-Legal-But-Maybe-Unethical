import logging

import requests

logger = logging.getLogger(__name__)

LRCLIB_BASE = "https://lrclib.net/api"


def get_lyrics(track_name: str, artist_name: str) -> str | None:
    """Fetch plain lyrics from Lrclib. Returns None if not found."""
    try:
        response = requests.get(
            f"{LRCLIB_BASE}/get",
            params={"track_name": track_name, "artist_name": artist_name},
            headers={"User-Agent": "Stalkify/1.0"},
            timeout=10,
        )
    except requests.RequestException:
        logger.warning("Lrclib request failed for '%s'.", track_name, exc_info=True)
        return None

    if response.status_code == 404:
        logger.info("No lyrics found for '%s' by '%s'.", track_name, artist_name)
        return None

    if not response.ok:
        logger.warning("Lrclib returned HTTP %d for '%s'.", response.status_code, track_name)
        return None

    lyrics = response.json().get("plainLyrics")
    return lyrics if lyrics else None
