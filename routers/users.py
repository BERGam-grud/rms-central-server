# routers/users.py — керування користувачами (тільки адмін)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from core.auth import admin_only, get_current_user
from core.database import fetchall, fetchone, execute
from core.auth import hash_password

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


@router.get("/")
def list_users(user: dict = Depends(admin_only)):
    rows = fetchall("""
        SELECT u.*, p.name AS post_name
        FROM   users u
        LEFT   JOIN posts p ON p.id = u.post_id
        ORDER  BY u.created_at DESC
    """)
    return [_fmt(r) for r in rows]


@router.post("/")
def create_user(body: UserCreate, user: dict = Depends(admin_only)):
    if fetchone("SELECT id FROM users WHERE username = %s", (body.username,)):
        raise HTTPException(400, "Логін вже зайнятий")
    if fetchone("SELECT id FROM users WHERE email = %s", (body.email,)):
        raise HTTPException(400, "Email вже зайнятий")

    execute("""
        INSERT INTO users (username, email, password_hash, role, post_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (body.username, body.email, hash_password(body.password), body.role, body.post_id))
    return {"ok": True}


@router.patch("/{user_id}")
def update_user(user_id: str, body: UserUpdate, user: dict = Depends(admin_only)):
    fields = {}
    if body.email     is not None: fields["email"]     = body.email
    if body.role      is not None: fields["role"]      = body.role
    if body.post_id   is not None: fields["post_id"]   = body.post_id
    if body.is_active is not None: fields["is_active"] = body.is_active
    if body.password  is not None: fields["password_hash"] = hash_password(body.password)

    if not fields:
        raise HTTPException(400, "Немає полів для оновлення")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    execute(f"UPDATE users SET {set_clause} WHERE id = %s", (*fields.values(), user_id))
    return {"ok": True}


@router.delete("/{user_id}")
def delete_user(user_id: str, user: dict = Depends(admin_only)):
    if str(user["id"]) == user_id:
        raise HTTPException(400, "Не можна видалити самого себе")
    execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
    return {"ok": True}


def _fmt(r: dict) -> dict:
    out = {}
    for k, v in r.items():
        if k == "password_hash":
            continue
        out[k] = str(v) if hasattr(v, "hex") else v.isoformat() if hasattr(v, "isoformat") else v
    return out
