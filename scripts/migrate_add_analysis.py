"""Add 'analysis' column to tracked_tracks table.

Usage: python -m scripts.migrate_add_analysis
"""

import psycopg2

from src.config import config

conn = psycopg2.connect(config.database_url)
try:
    with conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE tracked_tracks
            ADD COLUMN IF NOT EXISTS analysis TEXT
            """
        )
    conn.commit()
    print("Migration complete: 'analysis' column added to tracked_tracks.")
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
