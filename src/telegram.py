import logging
import re

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config
from src.spotify import Track

logger = logging.getLogger(__name__)

_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _escape(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#\+\-=|{}.!])", r"\\\1", text)


@retry(
    retry=retry_if_exception_type(
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    ),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _send(text: str) -> None:
    response = requests.post(
        _SEND_URL.format(token=config.telegram_bot_token),
        json={
            "chat_id": config.telegram_chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        },
        timeout=10,
    )
    response.raise_for_status()
    logger.info("Telegram message sent.")


def send_new_track_notification(track: Track, playlist_name: str) -> None:
    artists = ", ".join(track.artist_names)
    text = "\n".join(
        [
            "🎵 *Yeni şarkı eklendi\\!*",
            "",
            f"*{_escape(track.track_name)}*",
            f"👤 {_escape(artists)}",
            f"💿 {_escape(track.album_name)}",
            f"📋 {_escape(playlist_name)}",
            "",
            f"🔗 [Spotify'da aç]({track.spotify_url})",
        ]
    )
    _send(text)


def send_analysis_notification(analysis: str, lyrics_found: bool = True) -> None:
    header = "🧠 *Analiz*"
    if not lyrics_found:
        header += "\n_Şarkı sözleri bulunamadı, yorum şarkı adı ve sanatçıya göre yapıldı\\._"
    text = "\n".join(
        [
            header,
            "",
            _escape(analysis),
        ]
    )
    _send(text)


def send_error_notification(error_message: str) -> None:
    text = "\n".join(
        [
            "⚠️ *Spotify\\-OSINT \\— Sistem Hatası*",
            "",
            f"`{_escape(error_message)}`",
        ]
    )
    _send(text)
