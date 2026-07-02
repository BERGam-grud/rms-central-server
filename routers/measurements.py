# routers/measurements.py

from fastapi import APIRouter, Depends, Query
from typing import Optional
from core.auth import any_role
from core.database import fetchall

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


@router.get("/latest")
def get_latest(
    post_id:   Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    user: dict = Depends(any_role)
):
    where, params = [], []
    if post_id:   where.append("m.post_id = %s");   params.append(post_id)
    if device_id: where.append("m.device_id = %s"); params.append(device_id)
    if user["role"] == "operator" and user["post_id"]:
        where.append("m.post_id = %s"); params.append(str(user["post_id"]))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = fetchall(f"""
        SELECT DISTINCT ON (m.device_id, m.parameter)
               m.device_id, d.name AS device_name, d.type AS device_type,
               m.post_id, p.name AS post_name,
               m.parameter, m.value, m.unit, m.quality, m.recorded_at
        FROM   measurements m
        JOIN   devices d ON d.id = m.device_id
        JOIN   posts   p ON p.id = m.post_id
        {where_sql}
        ORDER  BY m.device_id, m.parameter, m.recorded_at DESC
    """, params or None)
    return [_fmt(r) for r in rows]


@router.get("/history")
def get_history(
    device_id: str = Query(...),
    parameter: str = Query(...),
    hours:     int = Query(default=2, ge=1, le=720),
    user: dict = Depends(any_role)
):
    """Історія для графіка — останні N годин."""
    rows = fetchall("""
        SELECT parameter, value, unit, recorded_at
        FROM   measurements
        WHERE  device_id  = %s
          AND  parameter  = %s
          AND  recorded_at >= NOW() - (%s || ' hours')::interval
        ORDER  BY recorded_at ASC
        LIMIT  1000
    """, (device_id, parameter, str(hours)))
    return [_fmt(r) for r in rows]


@router.get("/chart-init")
def chart_init(
    parameter: str = Query(...),
    hours:     int = Query(default=2, ge=1, le=24),
    user: dict = Depends(any_role)
):
    """Початкові дані для всіх графіків при відкритті сторінки."""
    where = []
    params_list = [parameter, str(hours)]
    if user["role"] == "operator" and user["post_id"]:
        where.append("AND m.post_id = %s")
        params_list.append(str(user["post_id"]))

    rows = fetchall(f"""
        SELECT m.device_id, m.parameter, m.value, m.unit, m.recorded_at
        FROM   measurements m
        WHERE  m.parameter = %s
          AND  m.recorded_at >= NOW() - (%s || ' hours')::interval
          {''.join(where)}
        ORDER  BY m.recorded_at ASC
        LIMIT  2000
    """, params_list)
    return [_fmt(r) for r in rows]


@router.get("/archive")
def get_archive(
    post_id:   Optional[str] = Query(None),
    parameter: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    limit:     int = Query(default=500, le=5000),
    user: dict = Depends(any_role)
):
    where, params = [], []
    if post_id:   where.append("post_id = %s");      params.append(post_id)
    if parameter: where.append("parameter = %s");    params.append(parameter)
    if date_from: where.append("recorded_at >= %s"); params.append(date_from)
    if date_to:   where.append("recorded_at <= %s"); params.append(date_to)
    if user["role"] == "operator" and user["post_id"]:
        where.append("post_id = %s"); params.append(str(user["post_id"]))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    rows = fetchall(f"""
        SELECT device_id, post_id, parameter, value, unit, quality, recorded_at
        FROM   measurements {where_sql}
        ORDER  BY recorded_at DESC LIMIT %s
    """, params or None)
    return [_fmt(r) for r in rows]


def _fmt(r: dict) -> dict:
    return {
        k: (str(v) if hasattr(v, "hex") else
            v.isoformat() if hasattr(v, "isoformat") else
            float(v) if hasattr(v, "__float__") else v)
        for k, v in r.items()
    }