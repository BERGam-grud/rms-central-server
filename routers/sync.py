# routers/sync.py — приймає дані синхронізації від локальних постів

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from core.database import execute, fetchone, fetchall
from core.config import SYNC_API_KEY

router = APIRouter(prefix="/api/sync", tags=["sync"])


def verify_key(request: Request):
    key = request.headers.get("X-Sync-Key")
    if not key or key != SYNC_API_KEY:
        raise HTTPException(403, "Невірний API ключ")


class MeasurementIn(BaseModel):
    post_id:     str
    device_id:   str
    parameter:   str
    value:       float
    unit:        str
    quality:     Optional[int]  = 0
    recorded_at: str

class AlarmIn(BaseModel):
    post_id:      str
    device_id:    Optional[str] = None
    level:        str
    status:       str
    message:      str
    threshold:    Optional[float] = None
    actual_value: Optional[float] = None
    triggered_at: str
    resolved_at:  Optional[str]   = None

class SyncBody(BaseModel):
    measurements: List[MeasurementIn] = []

class AlarmBody(BaseModel):
    alarms: List[AlarmIn] = []


@router.post("/push")
async def push(body: SyncBody, request: Request):
    verify_key(request)
    saved = errors = 0
    for m in body.measurements:
        try:
            if not fetchone("SELECT id FROM posts WHERE id=%s", (m.post_id,)):
                continue
            execute("""
                INSERT INTO measurements
                    (post_id, device_id, parameter, value, unit,
                     quality, recorded_at, synced)
                VALUES (%s,%s,%s,%s,%s,%s,%s::timestamptz,TRUE)
                ON CONFLICT DO NOTHING
            """, (m.post_id, m.device_id, m.parameter,
                  m.value, m.unit, m.quality or 0, m.recorded_at))
            saved += 1
        except Exception:
            errors += 1
    return {"ok": True, "saved": saved, "errors": errors}


@router.post("/push-alarms")
async def push_alarms(body: AlarmBody, request: Request):
    verify_key(request)
    saved = 0
    for a in body.alarms:
        try:
            if not fetchone("SELECT id FROM posts WHERE id=%s", (a.post_id,)):
                continue
            execute("""
                INSERT INTO alarms
                    (post_id, device_id, level, status, message,
                     threshold, actual_value, triggered_at, resolved_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::timestamptz,%s::timestamptz)
                ON CONFLICT DO NOTHING
            """, (a.post_id, a.device_id, a.level, a.status, a.message,
                  a.threshold, a.actual_value, a.triggered_at, a.resolved_at))
            saved += 1
        except Exception:
            pass
    return {"ok": True, "saved": saved}


@router.get("/status")
async def status(request: Request):
    verify_key(request)
    rows = fetchall("""
        SELECT p.name,
               COUNT(m.id) FILTER (WHERE m.synced=TRUE)  AS synced,
               COUNT(m.id) FILTER (WHERE m.synced=FALSE) AS pending,
               MAX(m.recorded_at) AS last_record
        FROM   posts p
        LEFT   JOIN measurements m ON m.post_id=p.id
        GROUP  BY p.id, p.name ORDER BY p.name
    """)
    return rows
