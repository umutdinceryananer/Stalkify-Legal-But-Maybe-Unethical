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

    def get_playlist_tracks(
        self,
        playlist_id: str,
        known_ids: set[str] | None = None,
        expected_new: int | None = None,
    ) -> list[Track]:
        """Scrape tracks from a public Spotify playlist via the web player.

        known_ids=None  → first run: full top-to-bottom scan, returns all tracks.
        known_ids={...} → incremental scan: jumps to the end of the playlist,
                          scrolls upward, and stops as soon as a known track ID
                          is found. Returns only the newly added tracks in
                          playlist order (oldest-first among new ones).
        expected_new    → if provided, stop collecting as soon as this many new
                          tracks have been found (prevents over-scanning).
        """
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

            if known_ids is None:
                # Full scan: scroll top-to-bottom and collect every track.
                # Spotify uses virtual scroll — rows leaving the viewport are
                # removed from the DOM. Staleness is detected by whether new
                # track IDs were found, not by DOM element count.
                stale_rounds = 0
                while stale_rounds < 5:
                    rows = page.query_selector_all('[data-testid="tracklist-row"]')
                    new_found = False

                    for row in rows:
                        track_link = row.query_selector('a[href*="/track/"]')
                        if not track_link:
                            continue
                        href = track_link.get_attribute("href") or ""
                        track_id = href.split("/track/")[-1].split("?")[0]
                        if not track_id or track_id in seen_ids:
                            continue
                        seen_ids.add(track_id)
                        new_found = True
                        tracks.append(self._build_track(track_link, track_id, row))

                    stale_rounds = 0 if new_found else stale_rounds + 1
                    page.evaluate(
                        "const r = document.querySelectorAll('[data-testid=\"tracklist-row\"]');"
                        "if (r.length) r[r.length - 1].scrollIntoView({block: 'end'});"
                    )
                    page.wait_for_timeout(1000)

            else:
                # Incremental scan: position at the end of the playlist first,
                # then scroll upward collecting unknown tracks until a known ID
                # is found. This avoids scanning the entire playlist on every run
                # and eliminates false positives from mid-playlist scraper drift.

                # Phase 1: fast-scroll to the physical end of the playlist.
                # Stop when the last visible track ID is stable across iterations.
                last_bottom_id: str | None = None
                stable_rounds = 0
                while stable_rounds < 3:
                    page.evaluate(
                        "const r = document.querySelectorAll('[data-testid=\"tracklist-row\"]');"
                        "if (r.length) r[r.length - 1].scrollIntoView({block: 'end'});"
                    )
                    page.wait_for_timeout(700)
                    rows = page.query_selector_all('[data-testid="tracklist-row"]')
                    bottom_id: str | None = None
                    for row in reversed(rows):
                        link = row.query_selector('a[href*="/track/"]')
                        if link:
                            href = link.get_attribute("href") or ""
                            tid = href.split("/track/")[-1].split("?")[0]
                            if tid:
                                bottom_id = tid
                                break
                    stable_rounds = stable_rounds + 1 if bottom_id == last_bottom_id else 0
                    last_bottom_id = bottom_id

                # Phase 2: scroll upward, collecting unknown tracks until a
                # known track ID appears in the viewport, or until expected_new
                # tracks have been collected (whichever comes first).
                stale_rounds = 0
                hit_known = False
                while stale_rounds < 3 and not hit_known:
                    rows = page.query_selector_all('[data-testid="tracklist-row"]')
                    new_found = False

                    for row in reversed(rows):
                        track_link = row.query_selector('a[href*="/track/"]')
                        if not track_link:
                            continue
                        href = track_link.get_attribute("href") or ""
                        track_id = href.split("/track/")[-1].split("?")[0]
                        if not track_id:
                            continue
                        if track_id in known_ids:
                            hit_known = True
                            break
                        if track_id not in seen_ids:
                            seen_ids.add(track_id)
                            new_found = True
                            tracks.append(self._build_track(track_link, track_id, row))
                            if expected_new is not None and len(tracks) >= expected_new:
                                hit_known = True  # collected exactly what we need
                                break

                    if hit_known:
                        break

                    stale_rounds = 0 if new_found else stale_rounds + 1
                    page.evaluate(
                        "const r = document.querySelectorAll('[data-testid=\"tracklist-row\"]');"
                        "if (r.length) r[0].scrollIntoView({block: 'start'});"
                    )
                    page.wait_for_timeout(1000)

                # Reverse so tracks are returned in playlist order (oldest first).
                tracks.reverse()

            browser.close()

        logger.info("Scraped %d track(s) from playlist %s.", len(tracks), playlist_id)
        return tracks

    def _build_track(self, track_link, track_id: str, row) -> "Track":
        """Extract full Track data from a DOM row element."""
        track_name = track_link.inner_text().strip()
        artist_links = row.query_selector_all('a[href*="/artist/"]')
        artist_names = [a.inner_text().strip() for a in artist_links]
        album_link = row.query_selector('a[href*="/album/"]')
        album_name = album_link.inner_text().strip() if album_link else ""
        return Track(
            track_id=track_id,
            track_name=track_name,
            artist_names=artist_names,
            album_name=album_name,
            spotify_url=f"{self._WEB_BASE}/track/{track_id}",
            added_at=None,
        )


    def get_playlist_info(self, playlist_id: str) -> dict | None:
        """Returns playlist name, owner ID, and track count, or None if inaccessible."""
        data = self._get(
            f"{self._API_BASE}/playlists/{playlist_id}",
            params={"fields": "id,name,owner(id),tracks(total)"},
        )
        if data is None:
            return None
        return {
            "name": data["name"],
            "owner_id": data["owner"]["id"],
            "track_count": data["tracks"]["total"],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = SpotifyClient()
    client.authenticate()
    print("Authentication successful. Access token obtained.")
