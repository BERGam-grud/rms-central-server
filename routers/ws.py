# routers/ws.py — WebSocket реального часу + push аварій

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.database import fetchall

router  = APIRouter()
clients: set[WebSocket] = set()


@router.websocket("/ws/live")
async def live(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            data = _get_live()
            await websocket.send_text(json.dumps(data, ensure_ascii=False, default=str))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        clients.discard(websocket)


async def broadcast_alarm(alarm: dict):
    """Викликається з колектора — миттєво надсилає аварію всім клієнтам."""
    msg = json.dumps({"type": "alarm", "alarm": alarm}, ensure_ascii=False, default=str)
    dead = set()
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    clients -= dead


def _get_live() -> dict:
    measurements = fetchall("""
        SELECT DISTINCT ON (m.device_id, m.parameter)
               m.device_id, d.name AS device_name, d.type AS device_type,
               m.post_id, p.name AS post_name,
               m.parameter, m.value, m.unit, m.recorded_at
        FROM   measurements m
        JOIN   devices d ON d.id = m.device_id
        JOIN   posts   p ON p.id = m.post_id
        ORDER  BY m.device_id, m.parameter, m.recorded_at DESC
    """)
    alarm_counts = fetchall("""
        SELECT level, COUNT(*) AS cnt FROM alarms
        WHERE  status = 'ACTIVE' GROUP BY level
    """)
    active_alarms = fetchall("""
        SELECT a.id, a.level, a.message, a.actual_value, a.threshold,
               a.triggered_at, a.status,
               p.name AS post_name, d.name AS device_name
        FROM   alarms a
        LEFT   JOIN posts   p ON p.id = a.post_id
        LEFT   JOIN devices d ON d.id = a.device_id
        WHERE  a.status = 'ACTIVE'
        ORDER  BY a.triggered_at DESC
        LIMIT  50
    """)
    return {
        "type":         "live",
        "measurements": measurements,
        "alarms":       {r["level"]: int(r["cnt"]) for r in alarm_counts},
        "active_alarms": active_alarms,
    }