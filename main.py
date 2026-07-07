"""
=============================================================
 РМС — Центральний сервер
 Деплой: Railway (railway.app)
=============================================================
"""

import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from routers import sync_v2

from routers import auth, posts, measurements, alarms, users, thresholds, sync
from routers import ws
from core.notifications import notification_worker
app.include_router(sync_v2.router)
app = FastAPI(
    title="РМС — Центральний сервер",
    version="1.0.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
  allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(measurements.router)
app.include_router(alarms.router)
app.include_router(thresholds.router)
app.include_router(users.router)
app.include_router(sync.router)
app.include_router(ws.router)

# Статичний веб-інтерфейс
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))
else:
    @app.get("/", include_in_schema=False)
    def index_placeholder():
        return HTMLResponse("""
        <html><body style="font-family:Arial;background:#0d0f12;color:#e8ecf2;
              display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">
          <div style="text-align:center">
            <h1 style="color:#00e5a0">РМС</h1>
            <p>Центральний сервер запущено</p>
            <a href="/api/docs" style="color:#4d9fff">→ API документація</a>
          </div>
        </body></html>
        """)


@app.on_event("startup")
async def startup():
    asyncio.create_task(notification_worker())


@app.get("/api/health")
def health():
    return {"status": "ok", "server": "central", "version": "1.0.0"}
