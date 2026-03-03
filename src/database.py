import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras

from src.config import config
from src.spotify import Track

logger = logging.getLogger(__name__)


@contextmanager
def _connection() -> Generator:
    conn = psycopg2.connect(config.database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_active_playlists() -> list[dict]:
    with _connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM playlists WHERE is_active = TRUE")
            return [dict(row) for row in cur.fetchall()]


def get_known_track_ids(playlist_id: str) -> set[str]:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT track_id FROM tracked_tracks WHERE playlist_id = %s",
                (playlist_id,),
            )
            return {row[0] for row in cur.fetchall()}


def is_first_run(playlist_id: str) -> bool:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM tracked_tracks WHERE playlist_id = %s",
                (playlist_id,),
            )
            return cur.fetchone()[0] == 0


def get_known_track_count(playlist_id: str) -> int:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM tracked_tracks WHERE playlist_id = %s",
                (playlist_id,),
            )
            return cur.fetchone()[0]


def add_playlist(playlist_id: str, name: str, owner_id: str) -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO playlists (id, name, owner_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, is_active = TRUE
                """,
                (playlist_id, name, owner_id),
            )
    logger.info("Playlist '%s' (%s) added.", name, playlist_id)


def deactivate_playlist(playlist_id: str) -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE playlists SET is_active = FALSE WHERE id = %s",
                (playlist_id,),
            )
    logger.info("Playlist %s deactivated.", playlist_id)


def save_tracks(tracks: list[Track], playlist_id: str) -> None:
    if not tracks:
        return

    with _connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO tracked_tracks
                    (track_id, playlist_id, track_name, artist_names,
                     album_name, spotify_url, added_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (track_id, playlist_id) DO NOTHING
                """,
                [
                    (
                        t.track_id,
                        playlist_id,
                        t.track_name,
                        t.artist_names,
                        t.album_name,
                        t.spotify_url,
                        t.added_at,
                    )
                    for t in tracks
                ],
            )
    logger.info("Saved %d tracks for playlist %s.", len(tracks), playlist_id)
