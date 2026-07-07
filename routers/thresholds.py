# routers/thresholds.py — пороги прив'язані до device_id

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.auth import any_role, admin_only, operator_only
from core.database import fetchall, fetchone, execute

router = APIRouter(prefix="/api/thresholds", tags=["thresholds"])


class ThresholdBody(BaseModel):
    device_id:   str            # ← обов'язково прив'язуємо до приладу
    post_id:     Optional[str] = None
    device_type: str
    parameter:   str
    warn_value:  float
    crit_value:  float
    unit:        Optional[str] = None


@router.get("/")
def list_thresholds(user: dict = Depends(admin_only)):
    rows = fetchall("""
        SELECT t.*, p.name AS post_name, d.name AS device_name
        FROM   thresholds t
        LEFT   JOIN posts   p ON p.id = t.post_id
        LEFT   JOIN devices d ON d.id = t.device_id
        ORDER  BY d.name, t.parameter
    """)
    return [_fmt(r) for r in rows]


@router.get("/for-device")
def for_device(
    device_id:   str,
    device_type: str,
    post_id:     Optional[str] = None,
    user: dict = Depends(any_role)
):
    """Пороги конкретного приладу — спочатку локальні (по device_id), потім глобальні."""
    rows = fetchall("""
        SELECT * FROM thresholds
        WHERE (device_id = %s)
           OR (device_id IS NULL
               AND device_type = %s
               AND (post_id = %s OR post_id IS NULL))
        ORDER BY
            CASE WHEN device_id = %s THEN 0 ELSE 1 END,
            parameter
    """, (device_id, device_type, post_id, device_id))
    return [_fmt(r) for r in rows]


@router.post("/")
def create_threshold(body: ThresholdBody, user: dict = Depends(operator_only)):
    if body.warn_value >= body.crit_value:
        raise HTTPException(400, "Критичне значення має бути більше за попереджувальне")

    # Перевіряємо чи вже є поріг для цього приладу + параметра
    existing = fetchone("""
        SELECT id FROM thresholds
        WHERE device_id = %s AND parameter = %s
    """, (body.device_id, body.parameter))

    if existing:
        # Оновлюємо існуючий
        execute("""
            UPDATE thresholds
            SET warn_value=%s, crit_value=%s, unit=%s, updated_at=NOW()
            WHERE id=%s
        """, (body.warn_value, body.crit_value, body.unit, existing["id"]))
    else:
        execute("""
            INSERT INTO thresholds
                (device_id, post_id, device_type, parameter,
                 warn_value, crit_value, unit, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (body.device_id, body.post_id, body.device_type,
              body.parameter, body.warn_value, body.crit_value,
              body.unit, str(user["id"])))
    return {"ok": True}


@router.patch("/{threshold_id}")
def update_threshold(threshold_id: str, body: ThresholdBody, user: dict = Depends(operator_only)):
    if body.warn_value >= body.crit_value:
        raise HTTPException(400, "Критичне значення має бути більше за попереджувальне")
    execute("""
        UPDATE thresholds
        SET warn_value=%s, crit_value=%s, unit=%s, updated_at=NOW()
        WHERE id=%s
    """, (body.warn_value, body.crit_value, body.unit, threshold_id))
    return {"ok": True}


@router.delete("/{threshold_id}")
def delete_threshold(threshold_id: str, user: dict = Depends(admin_only)):
    execute("DELETE FROM thresholds WHERE id=%s", (threshold_id,))
    return {"ok": True}


def _fmt(r: dict) -> dict:
    return {
        k: (str(v) if hasattr(v, "hex") else
            v.isoformat() if hasattr(v, "isoformat") else
            float(v) if hasattr(v, "__float__") else v)
        for k, v in r.items()
    }