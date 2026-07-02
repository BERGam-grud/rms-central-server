"""
Конфігурація центрального сервера.
Всі чутливі значення беруться зі змінних середовища Railway.
"""
import os

# ── База даних ───────────────────────────────────────────────
# Railway автоматично встановлює DATABASE_URL при додаванні PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Розбираємо DATABASE_URL → DB_CONFIG для psycopg2
def _parse_db_url(url: str) -> dict:
    if not url:
        return {}
    # postgresql://user:pass@host:port/dbname
    try:
        url = url.replace("postgresql://", "").replace("postgres://", "")
        user_pass, rest = url.split("@", 1)
        user, password   = user_pass.split(":", 1)
        host_port, dbname = rest.split("/", 1)
        if ":" in host_port:
            host, port = host_port.split(":", 1)
        else:
            host, port = host_port, "5432"
        return {
            "host":     host,
            "port":     int(port),
            "dbname":   dbname.split("?")[0],
            "user":     user,
            "password": password,
            "sslmode":  "require",
        }
    except Exception:
        return {}

DB_CONFIG = _parse_db_url(DATABASE_URL)

# ── JWT ──────────────────────────────────────────────────────
SECRET_KEY           = os.environ.get("SECRET_KEY", "change-me-in-railway-env")
ALGORITHM            = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 8

# ── Синхронізація ─────────────────────────────────────────────
# Цей ключ вказуйте в synchronizer.py на кожному локальному ПК
SYNC_API_KEY = os.environ.get("SYNC_API_KEY", "change-me-sync-key")

# ── Gmail ────────────────────────────────────────────────────
GMAIL_USER    = os.environ.get("GMAIL_USER", "")
GMAIL_PASS    = os.environ.get("GMAIL_PASS", "")
NOTIFY_EMAILS = [e.strip() for e in os.environ.get("NOTIFY_EMAILS", "").split(",") if e.strip()]

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
NOTIFY_CHAT_IDS  = [c.strip() for c in os.environ.get("NOTIFY_CHAT_IDS", "").split(",") if c.strip()]
NOTIFY_MIN_LEVEL = os.environ.get("NOTIFY_MIN_LEVEL", "WARNING")
NOTIFY_COOLDOWN_MIN = int(os.environ.get("NOTIFY_COOLDOWN_MIN", "30"))
