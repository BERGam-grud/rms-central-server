from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from core.config import SYNC_API_KEY
from core.database import get_conn

router = APIRouter(prefix="/api/sync/v2", tags=["sync-v2"])

ALLOWED_TABLES: dict[str, dict[str, Any]] = {
    "posts": {"pk": ("id",), "updated": "updated_at"},
    "devices": {"pk": ("id",), "updated": "updated_at"},
    "users": {"pk": ("id",), "updated": "updated_at"},
    "thresholds": {"pk": ("id",), "updated": "updated_at"},
    "alarms": {"pk": ("id",), "updated": "updated_at"},
    "measurements": {"pk": ("id", "recorded_at"), "updated": "updated_at"},
}


def verify_key(request: Request) -> None:
    key = request.headers.get("X-Sync-Key")
    if not key or key != SYNC_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid sync API key")


def get_table_config(table: str) -> dict[str, Any]:
    cfg = ALLOWED_TABLES.get(table)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Table is not allowed for sync: {table}")
    return cfg


class PushBody(BaseModel):
    table: str
    primary_key: list[str] = Field(default_factory=list)
    updated_column: str = "updated_at"
    rows: list[dict[str, Any]] = Field(default_factory=list)


def get_existing_columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def upsert_rows(conn, table: str, pk_cols: tuple[str, ...], updated_col: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    existing_cols = get_existing_columns(conn, table)
    count = 0
    with conn.cursor() as cur:
        for raw_row in rows:
            row = {k: v for k, v in raw_row.items() if k in existing_cols}
            if not row:
                continue
            missing_pk = [c for c in pk_cols if c not in row]
            if missing_pk:
                continue

            cols = list(row.keys())
            update_cols = [c for c in cols if c not in pk_cols]

            insert = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({values})").format(
                table=sql.Identifier(table),
                cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
                values=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
            )
            conflict = sql.SQL(" ON CONFLICT ({pk}) ").format(
                pk=sql.SQL(", ").join(map(sql.Identifier, pk_cols))
            )
            if update_cols:
                assignments = sql.SQL(", ").join(
                    sql.SQL("{col}=EXCLUDED.{col}").format(col=sql.Identifier(c))
                    for c in update_cols
                )
                where = sql.SQL("")
                if updated_col in cols and updated_col in existing_cols:
                    where = sql.SQL(" WHERE {table}.{updated} <= EXCLUDED.{updated}").format(
                        table=sql.Identifier(table),
                        updated=sql.Identifier(updated_col),
                    )
                query = insert + conflict + sql.SQL("DO UPDATE SET ") + assignments + where
            else:
                query = insert + conflict + sql.SQL("DO NOTHING")
            cur.execute(query, [row[c] for c in cols])
            count += 1
    conn.commit()
    return count


@router.post("/push")
async def push(body: PushBody, request: Request):
    verify_key(request)
    cfg = get_table_config(body.table)
    pk_cols = tuple(body.primary_key or cfg["pk"])
    if pk_cols != tuple(cfg["pk"]):
        raise HTTPException(status_code=400, detail="Primary key mismatch")
    if body.updated_column != cfg["updated"]:
        raise HTTPException(status_code=400, detail="Updated column mismatch")

    with get_conn() as conn:
        saved = upsert_rows(conn, body.table, pk_cols, cfg["updated"], body.rows)
    return {"ok": True, "table": body.table, "saved": saved}


@router.get("/pull")
async def pull(
    request: Request,
    table: str = Query(...),
    since: str = Query("1970-01-01T00:00:00+00:00"),
    limit: int = Query(300, ge=1, le=5000),
):
    verify_key(request)
    cfg = get_table_config(table)
    updated = cfg["updated"]
    with get_conn() as conn:
        existing_cols = get_existing_columns(conn, table)
        if updated not in existing_cols:
            raise HTTPException(status_code=400, detail=f"Table has no {updated} column")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                sql.SQL("SELECT * FROM {table} WHERE {updated} > %s ORDER BY {updated} ASC LIMIT %s").format(
                    table=sql.Identifier(table),
                    updated=sql.Identifier(updated),
                ),
                (since, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"ok": True, "table": table, "rows": rows}


@router.get("/tables")
async def tables(request: Request):
    verify_key(request)
    return {"ok": True, "tables": sorted(ALLOWED_TABLES.keys())}
