# -*- coding: utf-8 -*-
"""
SmartMeet Agent Suite - FastAPI 服务入口
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes.recording import router as recording_router
from api.routes.websocket import router as ws_router

_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 从环境变量读取允许的 CORS 源，逗号分隔；开发环境默认放行本地常用地址
_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
).split(",")

app = FastAPI(
    title="SmartMeet Agent Suite API",
    description="多Agent智能会议分析系统 API 网关",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(recording_router)
app.include_router(ws_router)
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
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start()
