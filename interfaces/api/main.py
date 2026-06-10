
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

from utils.file_system import find_project_root

load_dotenv(dotenv_path=find_project_root() / ".env")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from utils.file_system import get_reports_dir
from interfaces.api.routes.recording import router as recording_router
from interfaces.api.routes.websocket import router as ws_router
from interfaces.api.routes.analyze import router as analyze_router
from interfaces.api.routes.render import router as render_router
from interfaces.api.routes.tasks import router as tasks_router
from interfaces.api.routes.deliver import router as deliver_router
from interfaces.api.routes.config import router as config_router
from interfaces.api.routes.reports import router as reports_router

_REPORTS_DIR = get_reports_dir()

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
).split(",")

from contextlib import asynccontextmanager
from arq import create_pool
from arq.connections import RedisSettings

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    app.state.redis = await create_pool(redis_settings)
    yield
    await app.state.redis.close()

app = FastAPI(
    title="SmartMeet Agent Suite API",
    description="多Agent智能会议分析系统 API 网关",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recording_router)
app.include_router(ws_router)
app.include_router(analyze_router)
app.include_router(render_router)
app.include_router(tasks_router)
app.include_router(deliver_router)
app.include_router(config_router)
app.include_router(reports_router)
app.mount("/reports", StaticFiles(directory=_REPORTS_DIR), name="reports")

@app.get("/")
async def root():
    return {
        "name": "SmartMeet Agent Suite API",
        "version": "1.0.0",
        "docs": "/docs",
        "websocket": "ws://localhost:8000/ws/meeting/{meeting_id}",
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

def start():
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() == "true"

    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print()
    console.print(Panel(
        "[bold cyan]SmartMeet API 服务已成功启动！[/bold cyan]\n"
        "✨ [green]服务运行在:[/green] http://127.0.0.1:8000\n"
        "📚 [green]接口文档:[/green] http://127.0.0.1:8000/docs\n\n"
        "💡 [bold yellow]现在你可以把这个窗口挂在后台，新开一个终端运行 CLI 指令啦！[/bold yellow]\n"
        "⚠️  按 [red]Ctrl+C[/red] 可以关闭本服务。",
        title="🚀 SmartMeet Agent Suite",
        expand=False,
        border_style="cyan"
    ))
    console.print()
    uvicorn.run("interfaces.api.main:app", host="0.0.0.0", port=8000, reload=reload_enabled)

if __name__ == "__main__":
    start()
