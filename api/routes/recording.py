# -*- coding: utf-8 -*-
"""
录制处理路由
- 处理本地音频文件上传
- 处理离线任务流水线（支持本地文件路径与在线 URL 抓取解析）
- 支持基于 Server-Sent Events（SSE）的进度推送
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from typing import Generator, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from loguru import logger

from services.pipeline import run_offline_pipeline
from schemas import JobConfig
from schemas.task_schema import TaskCreateResponse
from services.task_queue import task_queue

router = APIRouter(prefix="/api/v1/recording", tags=["recording"])

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "smartmeet_uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许通过 file_path 直接访问的基目录（resolve 后必须以此开头）
_ALLOWED_BASE_DIRS = (
    _UPLOAD_DIR.resolve(),
)


def _validate_path_safety(path: Path) -> Path:
    resolved = path.resolve()
    if not any(resolved == base or base in resolved.parents for base in _ALLOWED_BASE_DIRS):
        raise HTTPException(
            status_code=400,
            detail=f"文件路径不在允许的访问范围内",
        )
    return resolved

def _sse_event(stage: str, **kwargs) -> str:
    data = {"stage": stage, **kwargs}
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

def _resolve_input(
    file_id: str | None,
    file_path: str | None,
    url: str | None,
) -> tuple[str, Path | None]:
    meeting_id = str(uuid.uuid4())[:12]

    if file_id:
        files = list(_UPLOAD_DIR.glob(f"{file_id}.*"))
        if not files:
            raise HTTPException(status_code=404, detail="未找到上传的文件")
        actual_path = files[0]
    elif file_path:
        actual_path = _validate_path_safety(Path(file_path))
        if not actual_path.exists():
            raise HTTPException(status_code=400, detail="本地文件路径不存在")
    elif url:
        actual_path = None
    else:
        raise HTTPException(status_code=400, detail="必须提供 file_id, file_path 或 url 中的一个")

    return meeting_id, actual_path

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
    context: str = Form(None),
    num_speakers: int = Form(None),
    denoise_level: int = Form(1),
    extract_frames: bool = Form(True),
    job_config: str = Form(None, description="JobConfig JSON 字符串，控制流程开关"),
):
    """一键离线处理接口 (非流式)，支持 JobConfig 参数级流程控制"""
    meeting_id, actual_path = _resolve_input(file_id, file_path, url)

    # 解析 JobConfig（不传或解析失败时使用全开默认值）
    parsed_config = JobConfig()
    if job_config:
        try:
            parsed_config = JobConfig.model_validate_json(job_config)
        except Exception as e:
            logger.warning(f"job_config 解析失败，使用默认值: {e}")

    try:
        result = await run_offline_pipeline(
            input_path=actual_path,
            url=url,
            meeting_id=meeting_id,
            context=context,
            num_speakers=num_speakers,
            denoise_level=denoise_level,
            extract_frames=extract_frames,
            job_config=parsed_config,
        )
        return result
    except Exception as e:
        logger.exception("Error during process_recording_endpoint")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/async", response_model=TaskCreateResponse)
async def process_recording_async(
    background_tasks: BackgroundTasks,
    file_path: str = Form(None),
    file_id: str = Form(None),
    url: str = Form(None),
    context: str = Form(None),
    num_speakers: int = Form(None),
    denoise_level: int = Form(1),
    extract_frames: bool = Form(True),
    job_config: str = Form(None, description="JobConfig JSON 字符串，控制流程开关"),
):
    """一键离线处理接口 (纯异步流)，提交任务后立即返回 Task ID，由后台执行"""
    meeting_id, actual_path = _resolve_input(file_id, file_path, url)

    # 解析 JobConfig
    parsed_config = JobConfig()
    if job_config:
        try:
            parsed_config = JobConfig.model_validate_json(job_config)
        except Exception as e:
            logger.warning(f"job_config 解析失败，使用默认值: {e}")

    task_id = str(uuid.uuid4())
    
    # 1. 在数据库中创建 Pending 任务记录
    task_queue.task_service.create_task(task_id, meeting_id=meeting_id)
    
    # 2. 包装真正的耗时协程
    coro = run_offline_pipeline(
        input_path=actual_path,
        url=url,
        meeting_id=meeting_id,
        context=context,
        num_speakers=num_speakers,
        denoise_level=denoise_level,
        extract_frames=extract_frames,
        job_config=parsed_config,
    )
    
    # 3. 投递到后台执行
    background_tasks.add_task(
        task_queue.execute_task,
        task_id=task_id,
        coro=coro,
        webhook_urls=parsed_config.webhook_urls
    )
    
    return TaskCreateResponse(
        task_id=task_id,
        status="pending",
        message="Task submitted successfully. Please poll /api/v1/tasks/{task_id} for status."
    )

@router.post("/process/stream")
async def process_recording_stream(
    file_path: str = Form(None),
    file_id: str = Form(None),
    url: str = Form(None),
    context: str = Form(None),
    num_speakers: int = Form(None),
    denoise_level: int = Form(1),
    extract_frames: bool = Form(True),
    job_config: str = Form(None, description="JobConfig JSON 字符串，控制流程开关"),
):
    """基于 Server-Sent Events (SSE) 的音视频流式处理接口，支持 JobConfig 参数级流程控制"""
    meeting_id, actual_path = _resolve_input(file_id, file_path, url)

    # 解析 JobConfig
    parsed_config = JobConfig()
    if job_config:
        try:
            parsed_config = JobConfig.model_validate_json(job_config)
        except Exception as e:
            logger.warning(f"job_config 解析失败，使用默认值: {e}")

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
                        context=context,
                        num_speakers=num_speakers,
                        denoise_level=denoise_level,
                        extract_frames=extract_frames,
                        progress_callback=progress_callback,
                        job_config=parsed_config,
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
