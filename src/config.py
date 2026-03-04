import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


def _optional(key: str) -> str | None:
    value = os.getenv(key, "").strip()
    return value if value else None


@dataclass(frozen=True)
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    database_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    groq_api_key: str | None        # Issue 9 — optional until LLM integration


config = Config(
    spotify_client_id=_require("SPOTIFY_CLIENT_ID"),
    spotify_client_secret=_require("SPOTIFY_CLIENT_SECRET"),
    database_url=_require("DATABASE_URL"),
    telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
    telegram_chat_id=_require("TELEGRAM_CHAT_ID"),
    groq_api_key=_optional("GROQ_API_KEY"),
)
