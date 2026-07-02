"""
=============================================================
 Сповіщення: Gmail SMTP + Telegram бот
=============================================================
Налаштування в core/config.py:
  GMAIL_USER     = "your@gmail.com"
  GMAIL_PASS     = "xxxx xxxx xxxx xxxx"  # App Password
  TELEGRAM_TOKEN = "1234567890:AAF..."
  NOTIFY_EMAILS  = ["admin@example.com"]
  NOTIFY_CHAT_IDS= ["123456789"]
=============================================================
"""

import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import httpx

log = logging.getLogger(__name__)

# Імпорт конфігу — якщо поля відсутні повертаємо None
def _cfg(key, default=None):
    try:
        from core.config import __dict__ as _c
        return _c.get(key, default)
    except Exception:
        return default

# Черга сповіщень щоб не блокувати основний потік
_queue: asyncio.Queue = None

def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


# ── EMAIL ────────────────────────────────────────────────────

def send_email(subject: str, body: str):
    try:
        from core.config import GMAIL_USER, GMAIL_PASS, NOTIFY_EMAILS
        if not GMAIL_USER or not GMAIL_PASS or not NOTIFY_EMAILS:
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = ", ".join(NOTIFY_EMAILS)
        msg.attach(MIMEText(body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as srv:
            srv.login(GMAIL_USER, GMAIL_PASS)
            srv.sendmail(GMAIL_USER, NOTIFY_EMAILS, msg.as_string())
        log.info(f"✉ Email надіслано: {subject}")
    except ImportError:
        pass
    except Exception as e:
        log.error(f"✉ Помилка email: {e}")


# ── TELEGRAM ─────────────────────────────────────────────────

async def send_telegram(text: str):
    try:
        from core.config import TELEGRAM_TOKEN, NOTIFY_CHAT_IDS
        if not TELEGRAM_TOKEN or not NOTIFY_CHAT_IDS:
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            for chat_id in NOTIFY_CHAT_IDS:
                await client.post(url, json={
                    "chat_id":    chat_id,
                    "text":       text,
                    "parse_mode": "HTML",
                })
        log.info(f"✈ Telegram надіслано")
    except ImportError:
        pass
    except Exception as e:
        log.error(f"✈ Помилка Telegram: {e}")


# ── ФОРМАТУВАННЯ ПОВІДОМЛЕННЯ ────────────────────────────────

def format_alarm(alarm: dict) -> tuple[str, str, str]:
    """Повертає (subject, html_body, telegram_text)"""
    level    = alarm.get("level", "WARNING")
    message  = alarm.get("message", "—")
    post     = alarm.get("post_name", "—")
    device   = alarm.get("device_name", "—")
    actual   = alarm.get("actual_value", "—")
    threshold= alarm.get("threshold", "—")
    time_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    icons = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}
    icon  = icons.get(level, "⚠")

    subject = f"[РМС] {icon} {level}: {post}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;background:#13161b;color:#e8ecf2;padding:24px;border-radius:8px;border-left:4px solid {'#ff4560' if level=='CRITICAL' else '#f0c040'}">
      <h2 style="margin:0 0 16px;color:{'#ff4560' if level=='CRITICAL' else '#f0c040'}">{icon} {level}</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr><td style="color:#8a94a6;padding:4px 0">Пост:</td><td><b>{post}</b></td></tr>
        <tr><td style="color:#8a94a6;padding:4px 0">Прилад:</td><td>{device}</td></tr>
        <tr><td style="color:#8a94a6;padding:4px 0">Повідомлення:</td><td>{message}</td></tr>
        <tr><td style="color:#8a94a6;padding:4px 0">Факт. значення:</td><td><b style="color:{'#ff4560' if level=='CRITICAL' else '#f0c040'}">{actual}</b></td></tr>
        <tr><td style="color:#8a94a6;padding:4px 0">Поріг:</td><td>{threshold}</td></tr>
        <tr><td style="color:#8a94a6;padding:4px 0">Час:</td><td>{time_str}</td></tr>
      </table>
      <p style="margin-top:16px;font-size:12px;color:#4a5568">Система радіаційного моніторингу РМС</p>
    </div>"""

    tg = (f"{icon} <b>{level}</b>\n"
          f"📍 Пост: {post}\n"
          f"🔧 Прилад: {device}\n"
          f"📊 {message}\n"
          f"📈 Факт: <b>{actual}</b> | Поріг: {threshold}\n"
          f"🕐 {time_str}")

    return subject, html, tg


# ── ВОРКЕР ЧЕРГИ ─────────────────────────────────────────────

async def notification_worker():
    """Фоновий таск — читає з черги і надсилає сповіщення."""
    q = get_queue()
    log.info("✉ Notification worker запущено")
    while True:
        try:
            alarm = await q.get()
            subject, html, tg = format_alarm(alarm)

            # Email у окремому потоці щоб не блокувати
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_email, subject, html)

            # Telegram асинхронно
            await send_telegram(tg)

            q.task_done()
        except Exception as e:
            log.error(f"Notification worker помилка: {e}")
        await asyncio.sleep(0.1)


def enqueue_alarm(alarm: dict):
    """Додає аварію в чергу сповіщень (thread-safe)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(get_queue().put_nowait, alarm)
    except Exception:
        pass