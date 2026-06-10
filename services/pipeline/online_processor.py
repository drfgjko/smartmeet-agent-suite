
import asyncio
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from services.media_engine import (
    detect_language,
    diarize,
    DiarizationResult,
    preprocess,
    transcribe,
)
from workflows.meeting_workflow import run_meeting_pipeline
from services.integrations import create_llm_client, FeishuClient, JiraClient
from utils import find_project_root, dump_outputs_for_json, create_fallback_diarization

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

async def process_audio_capture(
    audio_bytes: bytes,
    meeting_id: str,
    denoise_level: int = 1,
    num_speakers: int | None = None,
) -> tuple[Any, DiarizationResult, dict[str, Any]]:

    from utils import get_tmp_dir
    tmp_base = get_tmp_dir()
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_ws_", dir=str(tmp_base)))
    try:
        audio_file = work_dir / "input_audio.wav"
        audio_file.write_bytes(audio_bytes)

        pre_result = await asyncio.to_thread(
            preprocess,
            input_files=[audio_file],
            work_dir=work_dir,
            denoise_level=denoise_level,
        )

        language = await detect_language(pre_result.audio_path)

        transcript = await transcribe(pre_result.audio_path, language=language)

        if len(transcript.segments) > 0:
            diar_result = await asyncio.to_thread(
                diarize,
                audio_path=pre_result.audio_path,
                transcript=transcript,
                num_speakers=num_speakers,
            )
        else:
            diar_result = create_fallback_diarization(transcript, language)

        llm_client = create_llm_client()
        jira_client = JiraClient()
        feishu_client = FeishuClient()

        final_state = await run_meeting_pipeline(
            meeting_id=meeting_id,
            transcript_text=diar_result.transcript_with_speakers,
            transcript=diar_result,
            llm_client=llm_client,
            jira_client=jira_client,
            feishu_client=feishu_client,
        )

        transcript_payload = {
            "segments": [
                {"start": segment.start, "end": segment.end, "text": segment.text}
                for segment in transcript.segments
            ],
            "language": language,
            "source": "asr",
        }
        return final_state, diar_result, transcript_payload
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(f"[ApplicationService] 已自动清理 WebSocket 临时工作目录: {work_dir}")

async def emit_agent_events(final_state: Any, emit: ProgressCallback) -> None:

    outputs = dump_outputs_for_json(final_state)

    for key in ("summary", "actions", "insights", "followup"):
        if outputs[key]:
            await emit(key, outputs[key])

    await emit(
        "completed",
        {
            "meeting_id": final_state.get("meeting_id", ""),
            "status": final_state.get("status", "COMPLETED"),
            "errors": final_state.get("errors", []),
        },
    )
