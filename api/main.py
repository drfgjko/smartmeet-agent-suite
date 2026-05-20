# -*- coding: utf-8 -*-
"""
SmartMeet Agent Suite - FastAPI 核心入口
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.recording import router as recording_router
from api.routes.websocket import router as ws_router

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(recording_router)
app.include_router(ws_router)

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
