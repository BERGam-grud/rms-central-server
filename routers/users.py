# routers/users.py — повне управління користувачами

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from core.auth import admin_only, get_current_user, hash_password
from core.database import fetchall, fetchone, execute

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username:  str
    email:     EmailStr
    password:  str
    role:      str = "guest"
    post_id:   Optional[str] = None


class UserUpdate(BaseModel):
    email:     Optional[EmailStr] = None
    role:      Optional[str]      = None
    post_id:   Optional[str]      = None
    is_active: Optional[bool]     = None
    password:  Optional[str]      = None
    username:  Optional[str]      = None


@router.get("/")
def list_users(user: dict = Depends(admin_only)):
    rows = fetchall("""
        SELECT u.id, u.username, u.email, u.role,
               u.post_id, u.is_active, u.last_login, u.created_at,
               p.name AS post_name
        FROM   users u
        LEFT   JOIN posts p ON p.id = u.post_id
        ORDER  BY u.created_at DESC
    """)
    return [_fmt(r) for r in rows]


@router.post("/")
def create_user(body: UserCreate, user: dict = Depends(admin_only)):
    if fetchone("SELECT id FROM users WHERE username=%s", (body.username,)):
        raise HTTPException(400, "Логін вже зайнятий")
    if fetchone("SELECT id FROM users WHERE email=%s", (body.email,)):
        raise HTTPException(400, "Email вже зайнятий")
    if body.role not in ("admin", "operator", "guest"):
        raise HTTPException(400, "Невірна роль")

    execute("""
        INSERT INTO users (username, email, password_hash, role, post_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (body.username, body.email,
          hash_password(body.password), body.role, body.post_id or None))
    return {"ok": True}


@router.get("/{user_id}")
def get_user(user_id: str, user: dict = Depends(admin_only)):
    row = fetchone("""
        SELECT u.*, p.name AS post_name
        FROM   users u LEFT JOIN posts p ON p.id = u.post_id
        WHERE  u.id = %s
    """, (user_id,))
    if not row:
        raise HTTPException(404, "Користувача не знайдено")
    return _fmt(row)


@router.patch("/{user_id}")
def update_user(user_id: str, body: UserUpdate, user: dict = Depends(admin_only)):
    # Не можна редагувати самого себе через цей ендпоінт (захист від блокування)
    target = fetchone("SELECT id, username FROM users WHERE id=%s", (user_id,))
    if not target:
        raise HTTPException(404, "Користувача не знайдено")

    fields = {}

    if body.username is not None:
        # Перевіряємо унікальність логіна
        exist = fetchone(
            "SELECT id FROM users WHERE username=%s AND id!=%s",
            (body.username, user_id)
        )
        if exist:
            raise HTTPException(400, "Логін вже зайнятий")
        fields["username"] = body.username

    if body.email is not None:
        exist = fetchone(
            "SELECT id FROM users WHERE email=%s AND id!=%s",
            (body.email, user_id)
        )
        if exist:
            raise HTTPException(400, "Email вже зайнятий")
        fields["email"] = body.email

    if body.role is not None:
        if body.role not in ("admin", "operator", "guest"):
            raise HTTPException(400, "Невірна роль")
        fields["role"] = body.role

    if body.post_id is not None:
        fields["post_id"] = body.post_id if body.post_id != "" else None

    if body.is_active is not None:
        # Не можна заблокувати самого себе
        if str(user["id"]) == user_id and not body.is_active:
            raise HTTPException(400, "Не можна заблокувати самого себе")
        fields["is_active"] = body.is_active

    if body.password is not None:
        if len(body.password) < 6:
            raise HTTPException(400, "Пароль має бути мінімум 6 символів")
        fields["password_hash"] = hash_password(body.password)

    if not fields:
        raise HTTPException(400, "Немає полів для оновлення")

    set_clause = ", ".join(f"{k}=%s" for k in fields)
    execute(
        f"UPDATE users SET {set_clause} WHERE id=%s",
        (*fields.values(), user_id)
    )
    return {"ok": True}


@router.delete("/{user_id}")
def delete_user(user_id: str, user: dict = Depends(admin_only)):
    if str(user["id"]) == user_id:
        raise HTTPException(400, "Не можна видалити самого себе")
    execute("UPDATE users SET is_active=FALSE WHERE id=%s", (user_id,))
    return {"ok": True}


def _fmt(r: dict) -> dict:
    out = {}
    for k, v in r.items():
        if k == "password_hash":
            continue
        out[k] = (str(v) if hasattr(v, "hex") else
                  v.isoformat() if hasattr(v, "isoformat") else v)
    return out
