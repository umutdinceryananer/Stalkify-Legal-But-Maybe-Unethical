import logging
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
from playwright_stealth import stealth_sync

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    """Convert text to Genius URL slug: lowercase, special chars removed, spaces to hyphens."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation (apostrophes, commas, etc.)
    text = re.sub(r"[\s_]+", "-", text)   # spaces/underscores → hyphens
    text = re.sub(r"-+", "-", text)        # collapse consecutive hyphens
    return text.strip("-")


def get_lyrics(track_name: str, artist_name: str) -> str | None:
    """Scrape lyrics from Genius by navigating directly to the lyrics page."""
    artist_slug = _slug(artist_name)
    track_slug = _slug(track_name)
    lyrics_url = f"https://genius.com/{artist_slug}-{track_slug}-lyrics"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        try:
            page = context.new_page()
            stealth_sync(page)

            logger.info("Fetching lyrics from %s", lyrics_url)
            response = page.goto(lyrics_url, timeout=15000)

            if response and response.status == 404:
                logger.info("No Genius page for '%s' by '%s'.", track_name, artist_name)
                return None

            try:
                page.wait_for_selector('[data-lyrics-container="true"]', timeout=10000)
            except PlaywrightTimeoutError:
                logger.info("Lyrics container not found for '%s'.", track_name)
                return None

            containers = page.query_selector_all('[data-lyrics-container="true"]')
            if not containers:
                return None

            lines = [container.inner_text() for container in containers]
            lyrics = "\n".join(lines).strip()
            lyrics = re.sub(r"\n{3,}", "\n\n", lyrics)

            return lyrics if lyrics else None

        except Exception:
            logger.warning("Genius scraping failed for '%s'.", track_name, exc_info=True)
            return None
        finally:
            context.close()
            browser.close()
