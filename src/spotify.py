import base64
import logging
import time
from dataclasses import dataclass
from datetime import datetime

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config

logger = logging.getLogger(__name__)


@dataclass
class Track:
    track_id: str
    track_name: str
    artist_names: list[str]
    album_name: str
    spotify_url: str
    added_at: datetime | None


class SpotifyClient:
    _TOKEN_URL = "https://accounts.spotify.com/api/token"
    _API_BASE = "https://api.spotify.com/v1"
    _FIELDS = (
        "items(added_at,track(id,name,artists(name),album(name),external_urls)),next"
    )

    def __init__(self) -> None:
        self._access_token: str | None = None

    def authenticate(self) -> None:
        credentials = base64.b64encode(
            f"{config.spotify_client_id}:{config.spotify_client_secret}".encode()
        ).decode()

        response = requests.post(
            self._TOKEN_URL,
            headers={"Authorization": f"Basic {credentials}"},
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        logger.info("Spotify authentication successful.")

    @property
    def _headers(self) -> dict:
        if not self._access_token:
            raise RuntimeError(
                "SpotifyClient is not authenticated. Call authenticate() first."
            )
        return {"Authorization": f"Bearer {self._access_token}"}

    @retry(
        retry=retry_if_exception_type(
            (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> dict | None:
        response = requests.get(
            url, headers=self._headers, params=params, timeout=10
        )

        if response.status_code in (403, 404):
            logger.warning(
                "Playlist inaccessible (HTTP %s) — skipping: %s",
                response.status_code,
                url,
            )
            return None

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            logger.warning("Rate limited. Waiting %d seconds.", retry_after)
            time.sleep(retry_after)
            return self._get(url, params)

        response.raise_for_status()
        return response.json()

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        tracks: list[Track] = []
        url = f"{self._API_BASE}/playlists/{playlist_id}/tracks"
        params: dict = {"fields": self._FIELDS, "limit": 100, "offset": 0}

        while url:
            data = self._get(url, params)
            if data is None:
                return []

            for item in data.get("items", []):
                track_data = item.get("track")
                if not track_data or not track_data.get("id"):
                    # Local files and deleted tracks have no ID
                    continue

                added_at_raw = item.get("added_at")
                tracks.append(
                    Track(
                        track_id=track_data["id"],
                        track_name=track_data["name"],
                        artist_names=[
                            a["name"] for a in track_data.get("artists", [])
                        ],
                        album_name=track_data.get("album", {}).get("name", ""),
                        spotify_url=track_data.get("external_urls", {}).get(
                            "spotify", ""
                        ),
                        added_at=(
                            datetime.fromisoformat(
                                added_at_raw.replace("Z", "+00:00")
                            )
                            if added_at_raw
                            else None
                        ),
                    )
                )

            url = data.get("next") or ""
            params = {}

        logger.info(
            "Fetched %d tracks from playlist %s.", len(tracks), playlist_id
        )
        return tracks


    def get_playlist_info(self, playlist_id: str) -> dict | None:
        """Returns playlist name and owner ID, or None if inaccessible."""
        data = self._get(
            f"{self._API_BASE}/playlists/{playlist_id}",
            params={"fields": "id,name,owner(id)"},
        )
        if data is None:
            return None
        return {
            "name": data["name"],
            "owner_id": data["owner"]["id"],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = SpotifyClient()
    client.authenticate()
    print("Authentication successful. Access token obtained.")
