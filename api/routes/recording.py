# -*- coding: utf-8 -*-
"""
Recording Routes
- 处理本地音频文件上传
- 处理离线任务流水线（支持本地文件路径与在线 URL 抓取解析）
- 支持 Server-Sent Events (SSE) 进度推送
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from typing import Generator, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from services.application_service import run_offline_pipeline

router = APIRouter(prefix="/api/v1/recording", tags=["recording"])

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "smartmeet_uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _sse_event(stage: str, **kwargs) -> str:
    data = {"stage": stage, **kwargs}
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传本地音视频文件，缓存于临时目录"""
    file_id = str(uuid.uuid4())
    ext = Path(file.filename or "upload").suffix
    save_path = _UPLOAD_DIR / f"{file_id}{ext}"

    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": save_path.stat().st_size,
        "path": str(save_path),
    }

@router.post("/process")
async def process_recording_endpoint(
    file_path: str = Form(None),
    file_id: str = Form(None),
    url: str = Form(None),
    template: str = Form("meeting_minutes"),
    context: str = Form(None),
    num_speakers: int = Form(None),
    denoise_level: int = Form(1),
    extract_frames: bool = Form(True),
):
    """一键离线处理接口 (非流式)"""
    meeting_id = str(uuid.uuid4())[:12]
    
    if file_id:
        files = list(_UPLOAD_DIR.glob(f"{file_id}.*"))
        if not files:
            raise HTTPException(status_code=404, detail="未找到上传的文件")
        actual_path: Path | None = files[0]
    elif file_path:
        actual_path = Path(file_path)
        if not actual_path.exists():
            raise HTTPException(status_code=400, detail="本地文件路径不存在")
    elif url:
        actual_path = None
    else:
        raise HTTPException(status_code=400, detail="必须提供 file_id, file_path 或 url 中的一个")

    try:
        result = await run_offline_pipeline(
            input_path=actual_path,
            url=url,
            meeting_id=meeting_id,
            template=template,
            context=context,
            num_speakers=num_speakers,
            denoise_level=denoise_level,
            extract_frames=extract_frames,
        )
        return result
    except Exception as e:
        logger.exception("Error during process_recording_endpoint")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/stream")
async def process_recording_stream(
    file_path: str = Form(None),
    file_id: str = Form(None),
    url: str = Form(None),
    template: str = Form("meeting_minutes"),
    context: str = Form(None),
    num_speakers: int = Form(None),
    denoise_level: int = Form(1),
    extract_frames: bool = Form(True),
):
    """基于 Server-Sent Events (SSE) 的音视频流式处理接口"""
    meeting_id = str(uuid.uuid4())[:12]
    
    if file_id:
        files = list(_UPLOAD_DIR.glob(f"{file_id}.*"))
        if not files:
            raise HTTPException(status_code=404, detail="未找到上传的文件")
        actual_path: Path | None = files[0]
    elif file_path:
        actual_path = Path(file_path)
        if not actual_path.exists():
            raise HTTPException(status_code=400, detail="本地文件路径不存在")
    elif url:
        actual_path = None
    else:
        raise HTTPException(status_code=400, detail="必须提供 file_id, file_path 或 url 中的一个")

    async def generate() -> Generator[str, None, None]:
        try:
            async def progress_callback(stage: str, details: dict[str, Any]):
                loop.call_soon_threadsafe(queue.put_nowait, _sse_event(stage, **details))

            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            async def worker():
                try:
                    res = await run_offline_pipeline(
                        input_path=actual_path,
                        url=url,
                        meeting_id=meeting_id,
                        template=template,
                        context=context,
                        num_speakers=num_speakers,
                        denoise_level=denoise_level,
                        extract_frames=extract_frames,
                        progress_callback=progress_callback,
                    )
                    await progress_callback("done", res)
                except Exception as ex:
                    logger.exception("Error in pipeline task")
                    await progress_callback("error", {"message": str(ex)})
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            asyncio.create_task(worker())

            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item

        except Exception as e:
            logger.exception("Error in process_recording_stream generator")
            yield _sse_event("error", message=str(e))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/scenes")
async def list_scenes():
    """获取系统支持的提示词模板和应用场景列表"""
    return [
        {"name": "meeting", "display": "会议", "description": "会议纪要、议题、决议、行动项"},
        {"name": "lecture", "display": "课堂", "description": "知识点、公式、习题、学习建议"},
        {"name": "interview", "display": "访谈", "description": "Q&A、观点、立场分析"},
        {"name": "brainstorm", "display": "灵感", "description": "想法、思维导图、行动建议"},
        {"name": "news", "display": "新闻", "description": "5W1H、引用、背景"},
        {"name": "exam", "display": "考试", "description": "闪卡、模拟题、要点清单"},
        {"name": "entertainment", "display": "娱乐", "description": "高光、金句、推荐指数"},
        {"name": "custom", "display": "自定义", "description": "自由定义输出格式"},
    ]
