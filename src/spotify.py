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
    _WEB_BASE = "https://open.spotify.com"

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
        """Scrape all tracks from a public Spotify playlist via the web player."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        tracks: list[Track] = []
        seen_ids: set[str] = set()
        url = f"{self._WEB_BASE}/playlist/{playlist_id}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(
                    '[data-testid="tracklist-row"]', timeout=20000
                )
            except PlaywrightTimeoutError:
                logger.warning(
                    "Playlist page timed out or no tracks found: %s", url
                )
                browser.close()
                return []

            # Scroll incrementally to trigger virtual-scroll loading
            stale_rounds = 0
            previous_count = 0
            while stale_rounds < 3:
                rows = page.query_selector_all('[data-testid="tracklist-row"]')
                if len(rows) == previous_count:
                    stale_rounds += 1
                else:
                    stale_rounds = 0
                    previous_count = len(rows)
                if rows:
                    rows[-1].scroll_into_view_if_needed()
                page.wait_for_timeout(800)

            # Extract track data from all loaded rows
            rows = page.query_selector_all('[data-testid="tracklist-row"]')
            for row in rows:
                track_link = row.query_selector('a[href*="/track/"]')
                if not track_link:
                    continue

                href = track_link.get_attribute("href") or ""
                track_id = href.split("/track/")[-1].split("?")[0]
                if not track_id or track_id in seen_ids:
                    continue
                seen_ids.add(track_id)

                track_name = track_link.inner_text().strip()
                artist_links = row.query_selector_all('a[href*="/artist/"]')
                artist_names = [a.inner_text().strip() for a in artist_links]
                album_link = row.query_selector('a[href*="/album/"]')
                album_name = album_link.inner_text().strip() if album_link else ""

                tracks.append(
                    Track(
                        track_id=track_id,
                        track_name=track_name,
                        artist_names=artist_names,
                        album_name=album_name,
                        spotify_url=f"{self._WEB_BASE}/track/{track_id}",
                        added_at=None,
                    )
                )

            browser.close()

        logger.info(
            "Scraped %d tracks from playlist %s.", len(tracks), playlist_id
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
