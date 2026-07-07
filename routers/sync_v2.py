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


def cfg(table: str) -> dict[str, Any]:
    item = ALLOWED_TABLES.get(table)
    if not item:
        raise HTTPException(status_code=400, detail=f"Table is not allowed for sync: {table}")
    return item


class PushBody(BaseModel):
    table: str
    primary_key: list[str] = Field(default_factory=list)
    updated_column: str = "updated_at"
    rows: list[dict[str, Any]] = Field(default_factory=list)


def existing_columns(conn, table: str) -> set[str]:
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
    cols_existing = existing_columns(conn, table)
    applied = 0
    with conn.cursor() as cur:
        for raw in rows:
            row = {k: v for k, v in raw.items() if k in cols_existing}
            if not row or any(pk not in row for pk in pk_cols):
                continue

            cols = list(row.keys())
            update_cols = [c for c in cols if c not in pk_cols]

            insert_sql = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({values})").format(
                table=sql.Identifier(table),
                cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
                values=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
            )
            conflict_sql = sql.SQL(" ON CONFLICT ({pk}) ").format(
                pk=sql.SQL(", ").join(map(sql.Identifier, pk_cols))
            )

            if update_cols:
                assignments = sql.SQL(", ").join(
                    sql.SQL("{col}=EXCLUDED.{col}").format(col=sql.Identifier(c))
                    for c in update_cols
                )
                # Newer update wins. This is what transports deleted_at too.
                where_sql = sql.SQL("")
                if updated_col in cols and updated_col in cols_existing:
                    where_sql = sql.SQL(" WHERE {table}.{updated} <= EXCLUDED.{updated}").format(
                        table=sql.Identifier(table),
                        updated=sql.Identifier(updated_col),
                    )
                q = insert_sql + conflict_sql + sql.SQL("DO UPDATE SET ") + assignments + where_sql
            else:
                q = insert_sql + conflict_sql + sql.SQL("DO NOTHING")

            cur.execute(q, [row[c] for c in cols])
            applied += cur.rowcount if cur.rowcount >= 0 else 1
    conn.commit()
    return applied


@router.post("/push")
def push(body: PushBody, request: Request):
    verify_key(request)
    table_cfg = cfg(body.table)
    pk_cols = tuple(body.primary_key) if body.primary_key else table_cfg["pk"]
    updated_col = body.updated_column or table_cfg["updated"]
    if tuple(pk_cols) != tuple(table_cfg["pk"]):
        raise HTTPException(400, "Invalid primary key for table")
    with get_conn() as conn:
        applied = upsert_rows(conn, body.table, pk_cols, updated_col, body.rows)
    return {"ok": True, "table": body.table, "received": len(body.rows), "applied": applied}


@router.get("/pull")
def pull(
    request: Request,
    table: str = Query(...),
    since: str = Query("1970-01-01T00:00:00+00:00"),
    limit: int = Query(500, ge=1, le=5000),
):
    verify_key(request)
    table_cfg = cfg(table)
    updated_col = table_cfg["updated"]
    with get_conn() as conn:
        cols = existing_columns(conn, table)
        if updated_col not in cols:
            raise HTTPException(400, f"Table {table} has no {updated_col}")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            q = sql.SQL("SELECT * FROM {table} WHERE {updated} > %s ORDER BY {updated} ASC LIMIT %s").format(
                table=sql.Identifier(table),
                updated=sql.Identifier(updated_col),
            )
            cur.execute(q, (since, limit))
            rows = [dict(r) for r in cur.fetchall()]
    return {"ok": True, "table": table, "rows": rows}


@router.get("/debug/{table}")
def debug_table(request: Request, table: str, limit: int = Query(20, ge=1, le=100)):
    verify_key(request)
    table_cfg = cfg(table)
    updated_col = table_cfg["updated"]
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            q = sql.SQL("SELECT * FROM {table} ORDER BY {updated} DESC LIMIT %s").format(
                table=sql.Identifier(table),
                updated=sql.Identifier(updated_col),
            )
            cur.execute(q, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
    return {"ok": True, "table": table, "rows": rows}
