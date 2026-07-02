# routers/auth.py — вхід та інформація про поточного користувача

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from core.auth import verify_password, create_token, get_current_user
from core.database import fetchone

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = fetchone("SELECT * FROM users WHERE username = %s AND is_active = TRUE", (form.username,))

    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невірний логін або пароль")

    # Оновлюємо last_login
    from core.database import execute
    execute("UPDATE users SET last_login = NOW() WHERE id = %s", (str(user["id"]),))

    token = create_token({"sub": str(user["id"]), "role": user["role"]})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":       str(user["id"]),
            "username": user["username"],
            "role":     user["role"],
            "post_id":  str(user["post_id"]) if user["post_id"] else None,
        }
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "id":       str(user["id"]),
        "username": user["username"],
        "email":    user["email"],
        "role":     user["role"],
        "post_id":  str(user["post_id"]) if user["post_id"] else None,
    }
