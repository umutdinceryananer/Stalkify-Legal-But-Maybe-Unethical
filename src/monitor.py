import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from src.config import config  # validates all required env vars at startup

    logger.info("Monitor stub running. Full implementation coming in Issue 4.")
