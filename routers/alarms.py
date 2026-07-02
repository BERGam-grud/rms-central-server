# routers/alarms.py — аварії + сповіщення

from fastapi import APIRouter, Depends, Query
from typing import Optional
from core.auth import any_role, operator_only
from core.database import fetchall, fetchone, execute
from core.notifications import enqueue_alarm

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


@router.get("/")
def get_alarms(
    post_id: Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    level:   Optional[str] = Query(None),
    limit:   int = Query(default=200, le=2000),
    user: dict = Depends(any_role)
):
    where, params = [], []
    if post_id: where.append("a.post_id = %s"); params.append(post_id)
    if status:  where.append("a.status = %s");  params.append(status)
    if level:   where.append("a.level = %s");   params.append(level)
    if user["role"] == "operator" and user["post_id"]:
        where.append("a.post_id = %s"); params.append(str(user["post_id"]))

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)

    rows = fetchall(f"""
        SELECT a.*, p.name AS post_name, d.name AS device_name
        FROM   alarms a
        LEFT   JOIN posts   p ON p.id = a.post_id
        LEFT   JOIN devices d ON d.id = a.device_id
        {where_sql}
        ORDER  BY a.triggered_at DESC
        LIMIT  %s
    """, params or None)
    return [_fmt(r) for r in rows]


@router.get("/active/count")
def active_count(user: dict = Depends(any_role)):
    rows = fetchall("""
        SELECT level, COUNT(*) AS cnt FROM alarms
        WHERE  status = 'ACTIVE' GROUP BY level
    """)
    return {r["level"]: int(r["cnt"]) for r in rows}


@router.patch("/{alarm_id}/resolve")
def resolve_alarm(alarm_id: str, body: dict = {}, user: dict = Depends(operator_only)):
    execute("""
        UPDATE alarms SET status='RESOLVED', resolved_at=NOW(),
               resolved_by=%s, notes=%s
        WHERE  id=%s
    """, (str(user["id"]), body.get("notes"), alarm_id))
    return {"ok": True}


@router.patch("/{alarm_id}/ignore")
def ignore_alarm(alarm_id: str, user: dict = Depends(operator_only)):
    execute("""
        UPDATE alarms SET status='IGNORED', resolved_at=NOW(), resolved_by=%s
        WHERE  id=%s
    """, (str(user["id"]), alarm_id))
    return {"ok": True}


def create_alarm_and_notify(alarm_data: dict):
    """
    Викликається з колектора або WebSocket воркера.
    Зберігає аварію і ставить в чергу сповіщень.
    """
    enqueue_alarm(alarm_data)


def _fmt(r: dict) -> dict:
    return {
        k: (str(v) if hasattr(v, "hex") else
            v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in r.items()
    }