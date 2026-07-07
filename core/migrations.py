from __future__ import annotations

import logging
from pathlib import Path

from core.database import get_conn

log = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run SQL files from ./migrations once at application startup."""
    base_dir = Path(__file__).resolve().parents[1]
    migrations_dir = base_dir / "migrations"
    if not migrations_dir.exists():
        log.info("No migrations directory found: %s", migrations_dir)
        return

    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        log.info("No SQL migrations found")
        return

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.commit()

            for path in files:
                cur.execute("SELECT 1 FROM schema_migrations WHERE filename=%s", (path.name,))
                if cur.fetchone():
                    continue
                log.info("Applying migration %s", path.name)
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations(filename) VALUES (%s)", (path.name,))
                conn.commit()
                log.info("Applied migration %s", path.name)
