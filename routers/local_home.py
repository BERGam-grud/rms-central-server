# routers/local_home.py — локальна головна сторінка поста/постів користувача

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from core.auth import any_role
from core.database import fetchall, fetchone

router = APIRouter(prefix="/api/local", tags=["local-home"])


def _table_exists(name: str) -> bool:
    row = fetchone("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        ) AS ok
    """, (name,))
    return bool(row and row.get("ok"))


def _allowed_post_ids(user: dict) -> list[str]:
    """Пости, які має бачити користувач у локальному режимі.

    admin бачить усі пости. operator/guest бачать тільки прив'язані пости:
    1) нова таблиця user_post_access, якщо вона існує;
    2) сумісність зі старою схемою users.post_id.
    """
    if user.get("role") == "admin":
        rows = fetchall("SELECT id FROM posts WHERE deleted_at IS NULL ORDER BY name")
        return [str(r["id"]) for r in rows]

    ids: set[str] = set()
    if _table_exists("user_post_access"):
        rows = fetchall("""
            SELECT post_id
            FROM user_post_access
            WHERE user_id=%s
        """, (str(user["id"]),))
        ids.update(str(r["post_id"]) for r in rows)

    if user.get("post_id"):
        ids.add(str(user["post_id"]))

    return list(ids)


def _preferred_parameter(device_type: str, params: list[str]) -> Optional[str]:
    prefs = {
        "PAED_GAMMA": ["dose_rate", "dose", "gamma"],
        "PFU": ["flow_rate", "filter_load", "activity"],
        "SPECTROMETER": ["activity", "peak_energy", "dose_rate"],
    }
    for p in prefs.get(device_type, []):
        if p in params:
            return p
    return params[0] if params else None


def _fmt_dt(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


@router.get("/home")
def local_home(user: dict = Depends(any_role)):
    post_ids = _allowed_post_ids(user)
    if not post_ids:
        return {"ok": True, "posts": [], "post_label": "Пост не прив'язано", "devices": []}

    posts = fetchall("""
        SELECT id, name, location, region
        FROM posts
        WHERE deleted_at IS NULL AND id::text = ANY(%s)
        ORDER BY name
    """, (post_ids,))

    devices = fetchall("""
        SELECT d.id, d.post_id, p.name AS post_name, d.name, d.type,
               d.serial_port, d.is_online, d.last_seen
        FROM devices d
        JOIN posts p ON p.id=d.post_id
        WHERE d.deleted_at IS NULL AND d.post_id::text = ANY(%s)
        ORDER BY p.name, d.type, d.name
    """, (post_ids,))

    dev_ids = [str(d["id"]) for d in devices]
    param_map: dict[str, list[str]] = {d: [] for d in dev_ids}
    latest_map: dict[str, dict] = {}
    if dev_ids:
        latest = fetchall("""
            SELECT DISTINCT ON (m.device_id, m.parameter)
                   m.device_id, m.parameter, m.value, m.unit, m.recorded_at
            FROM measurements m
            WHERE m.device_id::text = ANY(%s)
            ORDER BY m.device_id, m.parameter, m.recorded_at DESC
        """, (dev_ids,))
        for r in latest:
            did = str(r["device_id"])
            param_map.setdefault(did, []).append(r["parameter"])
            latest_map[f"{did}::{r['parameter']}"] = {
                "parameter": r["parameter"],
                "value": float(r["value"]) if r.get("value") is not None else None,
                "unit": r.get("unit"),
                "recorded_at": _fmt_dt(r.get("recorded_at")),
            }

    def fmt_post(p):
        return {
            "id": str(p["id"]),
            "name": p.get("name"),
            "location": p.get("location"),
            "region": p.get("region"),
        }

    def fmt_device(d):
        did = str(d["id"])
        params = param_map.get(did, [])
        preferred = _preferred_parameter(d.get("type"), params)
        return {
            "id": did,
            "post_id": str(d["post_id"]),
            "post_name": d.get("post_name"),
            "name": d.get("name"),
            "type": d.get("type"),
            "serial_port": d.get("serial_port"),
            "is_online": d.get("is_online"),
            "last_seen": _fmt_dt(d.get("last_seen")),
            "parameters": params,
            "preferred_parameter": preferred,
            "latest": latest_map.get(f"{did}::{preferred}") if preferred else None,
        }

    return {
        "ok": True,
        "posts": [fmt_post(p) for p in posts],
        "post_label": ", ".join(p.get("name") or str(p["id"]) for p in posts),
        "devices": [fmt_device(d) for d in devices],
    }


@router.get("/device-history")
def device_history(
    device_id: str = Query(...),
    parameter: str = Query(...),
    hours: int = Query(default=2, ge=1, le=720),
    user: dict = Depends(any_role),
):
    post_ids = _allowed_post_ids(user)
    if not post_ids:
        return []

    dev = fetchone("""
        SELECT id, post_id
        FROM devices
        WHERE id=%s AND deleted_at IS NULL
    """, (device_id,))
    if not dev:
        raise HTTPException(404, "Прилад не знайдено")

    if str(dev["post_id"]) not in post_ids and user.get("role") != "admin":
        raise HTTPException(403, "Немає доступу до цього приладу")

    rows = fetchall("""
        SELECT parameter, value, unit, recorded_at
        FROM measurements
        WHERE device_id=%s
          AND parameter=%s
          AND recorded_at >= NOW() - (%s || ' hours')::interval
        ORDER BY recorded_at ASC
        LIMIT 1000
    """, (device_id, parameter, str(hours)))

    return [
        {
            "parameter": r["parameter"],
            "value": float(r["value"]),
            "unit": r.get("unit"),
            "recorded_at": _fmt_dt(r.get("recorded_at")),
        }
        for r in rows
    ]
