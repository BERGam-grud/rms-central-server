# routers/posts.py — пости та прилади з нотифікацією колектора

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.auth import any_role, admin_only, operator_only
from core.database import fetchall, fetchone, execute
import httpx, asyncio, logging

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])

# Адреса колектора для hot-reload (колектор слухає на localhost:8001)
COLLECTOR_RELOAD_URL = "http://127.0.0.1:8001/reload"


class PostCreate(BaseModel):
    name:      str
    location:  Optional[str]   = None
    region:    Optional[str]   = None
    latitude:  Optional[float] = None
    longitude: Optional[float] = None

class PostUpdate(BaseModel):
    name:      Optional[str]   = None
    location:  Optional[str]   = None
    region:    Optional[str]   = None
    latitude:  Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool]  = None

class DeviceCreate(BaseModel):
    type:  str
    name:  str
    host:  str
    port:  int

class DeviceUpdate(BaseModel):
    type:  Optional[str] = None
    name:  Optional[str] = None
    host:  Optional[str] = None
    port:  Optional[int] = None


async def notify_collector():
    """Повідомляє колектор що список приладів змінився."""
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            await client.post(COLLECTOR_RELOAD_URL)
        log.info("Колектор отримав сигнал перезавантаження")
    except Exception:
        log.debug("Колектор недоступний на :8001 (нормально якщо не запущений)")


# ── ПОСТИ ───────────────────────────────────────────────────

@router.get("/")
def get_posts(user: dict = Depends(admin_only)):
    if user["role"] == "operator" and user["post_id"]:
        rows = fetchall("SELECT * FROM posts WHERE id=%s AND deleted_at IS NULL AND deleted_at IS NULL", (str(user["post_id"]),))
    else:
        rows = fetchall("SELECT * FROM posts WHERE deleted_at IS NULL ORDER BY name")
    return [_fmt_post(r) for r in rows]


@router.post("/")
def create_post(body: PostCreate, user: dict = Depends(admin_only)):
    execute("""
        INSERT INTO posts (name, location, region, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
    """, (body.name, body.location, body.region, body.latitude, body.longitude))
    return {"ok": True}


@router.get("/{post_id}")
def get_post(post_id: str, user: dict = Depends(admin_only)):
    row = fetchone("SELECT * FROM posts WHERE id=%s AND deleted_at IS NULL AND deleted_at IS NULL", (post_id,))
    if not row: raise HTTPException(404, "Пост не знайдено")
    return _fmt_post(row)


@router.patch("/{post_id}")
def update_post(post_id: str, body: PostUpdate, user: dict = Depends(admin_only)):
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()
              if k in {"name","location","region","latitude","longitude","is_active"}}
    if not fields: raise HTTPException(400, "Немає полів")
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    execute(f"UPDATE posts SET {set_clause}, updated_at=NOW() WHERE id=%s",
            (*fields.values(), post_id))
    return {"ok": True}


@router.delete("/{post_id}")
def delete_post(post_id: str, user: dict = Depends(admin_only)):
    execute("""
        UPDATE posts
        SET deleted_at = NOW(),
            updated_at = NOW(),
            is_active = FALSE
        WHERE id=%s
    """, (post_id,))
    return {"ok": True}




# ── КОРИСТУВАЧІ ПОСТА ───────────────────────────────────────

@router.get("/{post_id}/users")
def get_post_users(post_id: str, user: dict = Depends(admin_only)):
    post = fetchone("""
        SELECT id, name
        FROM posts
        WHERE id=%s AND deleted_at IS NULL
    """, (post_id,))

    if not post:
        raise HTTPException(status_code=404, detail="Пост не знайдено")

    assigned = fetchall("""
        SELECT id, username, email, role, post_id, is_active
        FROM users
        WHERE post_id=%s
          AND deleted_at IS NULL
        ORDER BY username
    """, (post_id,))

    available = fetchall("""
        SELECT id, username, email, role, post_id, is_active
        FROM users
        WHERE deleted_at IS NULL
          AND is_active=TRUE
          AND (post_id IS NULL OR post_id<>%s)
        ORDER BY username
    """, (post_id,))

    def fmt_user(u):
        return {
            "id": str(u["id"]),
            "username": u.get("username"),
            "email": u.get("email"),
            "role": u.get("role"),
            "post_id": str(u["post_id"]) if u.get("post_id") else None,
            "is_active": u.get("is_active"),
        }

    return {
        "ok": True,
        "post": {
            "id": str(post["id"]),
            "name": post.get("name"),
        },
        "assigned": [fmt_user(u) for u in assigned],
        "available": [fmt_user(u) for u in available],
    }


@router.post("/{post_id}/users/{user_id}")
def bind_user_to_post(post_id: str, user_id: str, user: dict = Depends(admin_only)):
    """Адмін: прив'язати користувача до поста."""
    post = fetchone("SELECT id FROM posts WHERE id=%s AND deleted_at IS NULL", (post_id,))
    if not post:
        raise HTTPException(404, "Пост не знайдено")

    target = fetchone("SELECT id, username, role FROM users WHERE id=%s AND deleted_at IS NULL", (user_id,))
    if not target:
        raise HTTPException(404, "Користувача не знайдено")

    execute("""
        UPDATE users
        SET post_id=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (post_id, user_id))
    return {"ok": True}


@router.delete("/{post_id}/users/{user_id}")
def unbind_user_from_post(post_id: str, user_id: str, user: dict = Depends(admin_only)):
    """Адмін: відв'язати користувача від поста."""
    target = fetchone("SELECT id FROM users WHERE id=%s AND post_id=%s AND deleted_at IS NULL", (user_id, post_id))
    if not target:
        raise HTTPException(404, "Користувача не знайдено у цьому пості")

    execute("""
        UPDATE users
        SET post_id=NULL,
            updated_at=NOW()
        WHERE id=%s
    """, (user_id,))
    return {"ok": True}


# ── ПРИЛАДИ ─────────────────────────────────────────────────

@router.get("/{post_id}/devices")
def get_devices(post_id: str, user: dict = Depends(admin_only)):
    rows = fetchall("SELECT * FROM devices WHERE post_id=%s AND deleted_at IS NULL AND deleted_at IS NULL ORDER BY type", (post_id,))
    return [_fmt_device(r) for r in rows]


@router.post("/{post_id}/devices")
async def create_device(post_id: str, body: DeviceCreate, user: dict = Depends(admin_only)):
    if not fetchone("SELECT id FROM posts WHERE id=%s AND deleted_at IS NULL", (post_id,)):
        raise HTTPException(404, "Пост не знайдено")

    # Перевіряємо чи порт вже зайнятий іншим приладом
    existing = fetchone("SELECT id, name FROM devices WHERE serial_port=%s AND deleted_at IS NULL",
                        (f"{body.host}:{body.port}",))
    if existing:
        raise HTTPException(400, f"Порт {body.port} вже використовує прилад '{existing['name']}'")

    execute("""
        INSERT INTO devices (post_id, type, name, serial_port)
        VALUES (%s, %s, %s, %s)
    """, (post_id, body.type, body.name, f"{body.host}:{body.port}"))

    # Повідомляємо колектор — він одразу почне слухати новий порт
    await notify_collector()
    return {"ok": True}


@router.patch("/{post_id}/devices/{device_id}")
async def update_device(post_id: str, device_id: str,
                        body: DeviceUpdate, user: dict = Depends(admin_only)):
    dev = fetchone("SELECT * FROM devices WHERE id=%s AND post_id=%s AND deleted_at IS NULL AND deleted_at IS NULL",
                   (device_id, post_id))
    if not dev: raise HTTPException(404, "Прилад не знайдено")

    fields = {}
    if body.type: fields["type"] = body.type
    if body.name: fields["name"] = body.name

    # Оновлення IP або порту
    old_sp = dev["serial_port"] or "0.0.0.0:0"
    old_parts = old_sp.rsplit(":", 1)
    old_host = old_parts[0] if len(old_parts) == 2 else "0.0.0.0"
    old_port = old_parts[1] if len(old_parts) == 2 else "0"

    new_host = body.host if body.host is not None else old_host
    new_port = str(body.port) if body.port is not None else old_port
    new_sp   = f"{new_host}:{new_port}"

    if new_sp != old_sp:
        # Перевіряємо конфлікт портів
        conflict = fetchone(
            "SELECT id FROM devices WHERE serial_port=%s AND id!=%s AND deleted_at IS NULL",
            (new_sp, device_id)
        )
        if conflict:
            raise HTTPException(400, f"Порт {new_port} вже зайнятий")
        fields["serial_port"] = new_sp

    if not fields: raise HTTPException(400, "Немає полів для оновлення")

    set_clause = ", ".join(f"{k}=%s" for k in fields)
    execute(f"UPDATE devices SET {set_clause}, updated_at=NOW() WHERE id=%s AND post_id=%s",
            (*fields.values(), device_id, post_id))

    # Повідомляємо колектор — він зупинить старий сервер і запустить новий
    await notify_collector()
    return {"ok": True}


@router.delete("/{post_id}/devices/{device_id}")
async def delete_device(post_id: str, device_id: str, user: dict = Depends(admin_only)):
    execute("""
        UPDATE devices
        SET deleted_at = NOW(),
            updated_at = NOW(),
            is_online = FALSE
        WHERE id=%s AND post_id=%s
    """, (device_id, post_id))
    await notify_collector()
    return {"ok": True}


@router.get("/{post_id}/summary")
def post_summary(post_id: str, user: dict = Depends(admin_only)):
    devices  = fetchall("SELECT * FROM devices WHERE post_id=%s AND deleted_at IS NULL AND deleted_at IS NULL", (post_id,))
    readings = fetchall("""
        SELECT DISTINCT ON (device_id, parameter)
               device_id, parameter, value, unit, recorded_at
        FROM   measurements WHERE post_id=%s
        ORDER  BY device_id, parameter, recorded_at DESC
    """, (post_id,))
    alarms = fetchone("""
        SELECT COUNT(*) FILTER (WHERE level='CRITICAL') AS crit,
               COUNT(*) FILTER (WHERE level='WARNING')  AS warn
        FROM   alarms WHERE post_id=%s AND status='ACTIVE'
    """, (post_id,))
    return {
        "devices":  [_fmt_device(d) for d in devices],
        "readings": [_fmt_meas(r) for r in readings],
        "alarms":   {"critical": int(alarms["crit"]),
                     "warning":  int(alarms["warn"])} if alarms else {"critical":0,"warning":0},
    }


def _fmt_post(r):
    return {"id":str(r["id"]),"name":r["name"],"location":r["location"],
            "region":r["region"],
            "latitude":float(r["latitude"]) if r.get("latitude") else None,
            "longitude":float(r["longitude"]) if r.get("longitude") else None,
            "is_active":r["is_active"],
            "created_at":r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at":r["updated_at"].isoformat() if r.get("updated_at") else None,
            "deleted_at":r["deleted_at"].isoformat() if r.get("deleted_at") else None}

def _fmt_device(r):
    sp=r.get("serial_port") or ""
    parts=sp.rsplit(":",1)
    host=parts[0] if len(parts)==2 else sp
    port=int(parts[1]) if len(parts)==2 and parts[1].isdigit() else None
    return {"id":str(r["id"]),"post_id":str(r["post_id"]),"type":r["type"],
            "name":r["name"],"host":host,"port":port,"serial_port":sp,
            "is_online":r["is_online"],
            "last_seen":r["last_seen"].isoformat() if r.get("last_seen") else None}



def _fmt_post_user(r):
    return {
        "id": str(r["id"]),
        "username": r.get("username"),
        "email": r.get("email"),
        "role": r.get("role"),
        "post_id": str(r["post_id"]) if r.get("post_id") else None,
        "is_active": r.get("is_active"),
        "last_login": r["last_login"].isoformat() if r.get("last_login") else None,
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }

def _fmt_meas(r):
    return {k:(str(v) if hasattr(v,"hex") else v.isoformat() if hasattr(v,"isoformat")
               else float(v) if hasattr(v,"__float__") else v) for k,v in r.items()}