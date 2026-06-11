
import os
import asyncio
from pathlib import Path
from loguru import logger
from arq.connections import RedisSettings
from dotenv import load_dotenv

from utils.file_system import find_project_root
load_dotenv(dotenv_path=find_project_root() / ".env")

from services.pipeline import run_offline_pipeline
from schemas import JobConfig

async def startup(ctx):
    logger.info("ARQ Worker is starting...")

async def shutdown(ctx):
    logger.info("ARQ Worker is shutting down...")

async def background_offline_pipeline(
    ctx,
    input_path: str | None,
    url: str | None,
    meeting_id: str,
    num_speakers: int | None = None,
    denoise_level: int = 1,
    extract_frames: bool = True,
    job_config_dict: dict | None = None,
):
    logger.info(f"Worker started offline pipeline for meeting: {meeting_id}")

    actual_path = Path(input_path) if input_path else None
    parsed_config = JobConfig(**job_config_dict) if job_config_dict else JobConfig()

    try:
        async def progress_callback(stage: str, details: dict):
            import json
            redis_client = ctx['redis']
            channel = f"channel:progress:{meeting_id}"
            payload = {"stage": stage, **details}
            await redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))

        result = await run_offline_pipeline(
            input_path=actual_path,
            url=url,
            meeting_id=meeting_id,
            num_speakers=num_speakers,
            denoise_level=denoise_level,
            extract_frames=extract_frames,
            progress_callback=progress_callback,
            job_config=parsed_config,
        )
        await progress_callback("done", result)
        logger.info(f"Worker successfully finished offline pipeline for meeting: {meeting_id}")
        return result
    except Exception as e:
        logger.exception(f"Worker failed on offline pipeline for meeting: {meeting_id}")
        try:
            await progress_callback("error", {"message": str(e)})
        except Exception:
            pass
        raise e

class WorkerSettings:
    functions = [background_offline_pipeline]
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 3600  
    max_jobs = 10
    allow_abort_jobs = True
