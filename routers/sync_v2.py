# routers/sync_v2.py — універсальна двостороння синхронізація

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Any
from psycopg2 import sql
from psycopg2.extras import execute_values, RealDictCursor

from core.database import get_conn
from core.config import SYNC_API_KEY

router = APIRouter(prefix="/api/sync/v2", tags=["sync-v2"])


SYNC_TABLES = {
    "posts": {
        "primary_keys": ("id",),
        "watermark_column": "updated_at",
        "direction": "bidirectional",
    },
    "users": {
        "primary_keys": ("id",),
        "watermark_column": "updated_at",
        "direction": "bidirectional",
    },
    "devices": {
        "primary_keys": ("id",),
        "watermark_column": "updated_at",
        "direction": "bidirectional",
    },
    "thresholds": {
        "primary_keys": ("id",),
        "watermark_column": "updated_at",
        "direction": "bidirectional",
    },
    "alarms": {
        "primary_keys": ("id",),
        "watermark_column": "updated_at",
        "direction": "bidirectional",
    },
    "measurements": {
        "primary_keys": ("id", "recorded_at"),
        "watermark_column": "updated_at",
        "direction": "push",
    },
}


class PushBody(BaseModel):
    rows: list[dict[str, Any]] = []


def verify_key(request: Request):
    key = request.headers.get("X-Sync-Key")
    if not key or key != SYNC_API_KEY:
        raise HTTPException(403, "Невірний API ключ")


def get_table_config(table_name: str) -> dict:
    cfg = SYNC_TABLES.get(table_name)
    if not cfg:
        raise HTTPException(404, f"Таблиця не дозволена для sync: {table_name}")
    return cfg


def get_columns(conn, table_name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
        """, (table_name,))
        return [r[0] for r in cur.fetchall()]


def upsert_rows(conn, table_name: str, primary_keys: tuple[str, ...], rows: list[dict]) -> int:
    if not rows:
        return 0

    db_columns = set(get_columns(conn, table_name))
    columns = [c for c in rows[0].keys() if c in db_columns]
    if not columns:
        return 0

    values = [[row.get(c) for c in columns] for row in rows]
    update_columns = [c for c in columns if c not in primary_keys]

    if update_columns:
        assignments = sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
            for c in update_columns
        )
        if "updated_at" in columns and "updated_at" in db_columns:
            conflict_action = sql.SQL("DO UPDATE SET {} WHERE EXCLUDED.updated_at >= {}.updated_at").format(
                assignments,
                sql.Identifier(table_name),
            )
        else:
            conflict_action = sql.SQL("DO UPDATE SET {}").format(assignments)
    else:
        conflict_action = sql.SQL("DO NOTHING")

    query = sql.SQL("""
        INSERT INTO {} ({}) VALUES %s
        ON CONFLICT ({}) {}
    """).format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(map(sql.Identifier, primary_keys)),
        conflict_action,
    )

    with conn.cursor() as cur:
        execute_values(cur, query.as_string(conn), values, page_size=500)
    return len(rows)


@router.post("/push/{table_name}")
async def push_table(table_name: str, body: PushBody, request: Request):
    verify_key(request)
    cfg = get_table_config(table_name)
    if cfg["direction"] not in ("push", "bidirectional"):
        raise HTTPException(400, f"PUSH заборонено для {table_name}")

    with get_conn() as conn:
        try:
            saved = upsert_rows(conn, table_name, cfg["primary_keys"], body.rows)
            conn.commit()
            return {"ok": True, "table": table_name, "saved": saved}
        except Exception as e:
            conn.rollback()
            raise HTTPException(500, str(e))


@router.get("/pull/{table_name}")
async def pull_table(
    table_name: str,
    request: Request,
    since: str = Query("1970-01-01T00:00:00+00:00"),
    limit: int = Query(500, ge=1, le=5000),
):
    verify_key(request)
    cfg = get_table_config(table_name)
    if cfg["direction"] not in ("pull", "bidirectional"):
        raise HTTPException(400, f"PULL заборонено для {table_name}")

    watermark_column = cfg["watermark_column"]

    with get_conn() as conn:
        db_columns = set(get_columns(conn, table_name))
        if watermark_column not in db_columns:
            raise HTTPException(500, f"У таблиці {table_name} немає {watermark_column}")

        query = sql.SQL("""
            SELECT * FROM {}
            WHERE {} > %s::timestamptz
            ORDER BY {} ASC
            LIMIT %s
        """).format(
            sql.Identifier(table_name),
            sql.Identifier(watermark_column),
            sql.Identifier(watermark_column),
        )
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (since, limit))
            rows = [dict(r) for r in cur.fetchall()]

    return {"ok": True, "table": table_name, "rows": rows}


@router.get("/tables")
async def sync_tables(request: Request):
    verify_key(request)
    return {"ok": True, "tables": SYNC_TABLES}
