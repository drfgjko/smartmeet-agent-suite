# -*- coding: utf-8 -*-
"""
Application service for recording processing flows.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from services.media_engine import (
    align_frames_to_subtitles,
    detect_language,
    diarize,
    DiarizationResult,
    DiarizedSegment,
    download_audio,
    download_video,
    extract_keyframes,
    parse_link,
    preprocess,
    transcribe,
)
from workflows.meeting_workflow import run_meeting_pipeline

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def _model_dump_if_needed(value: Any) -> Any:
    if value is not None and hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _serialize_agent_outputs(final_state: Any) -> dict[str, Any]:
    return {
        "summary": _model_dump_if_needed(getattr(final_state, "summary", None)),
        "actions": _model_dump_if_needed(getattr(final_state, "actions", None)),
        "insights": _model_dump_if_needed(getattr(final_state, "insights", None)),
        "followup": _model_dump_if_needed(getattr(final_state, "followup", None)),
    }


async def process_audio_capture(
    audio_bytes: bytes,
    meeting_id: str,
    denoise_level: int = 1,
    num_speakers: int | None = None,
) -> tuple[Any, DiarizationResult, dict[str, Any]]:
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_ws_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_file = work_dir / "input_audio.wav"
    with open(audio_file, "wb") as file_obj:
        file_obj.write(audio_bytes)

    pre_result = await asyncio.to_thread(
        preprocess,
        input_files=[audio_file],
        work_dir=work_dir,
        denoise_level=denoise_level,
    )
    language = await asyncio.to_thread(detect_language, pre_result.audio_path)
    transcript = await asyncio.to_thread(transcribe, pre_result.audio_path, language=language)

    if len(transcript.segments) > 0:
        diar_result = await asyncio.to_thread(
            diarize,
            audio_path=pre_result.audio_path,
            transcript=transcript,
            num_speakers=num_speakers,
        )
    else:
        diar_result = DiarizationResult(
            segments=[
                DiarizedSegment(segment.start, segment.end, segment.text, "Speaker 1")
                for segment in transcript.segments
            ],
            num_speakers=1,
            speakers=["Speaker 1"],
            language=language,
        )

    final_state = await run_meeting_pipeline(
        meeting_id=meeting_id,
        transcript_text=diar_result.transcript_with_speakers,
        transcript=diar_result,
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


async def emit_agent_events(final_state: Any, emit: ProgressCallback) -> None:
    outputs = _serialize_agent_outputs(final_state)
    for key in ("summary", "actions", "insights", "followup"):
        if outputs[key]:
            await emit(key, outputs[key])
    await emit(
        "completed",
        {
            "meeting_id": getattr(final_state, "meeting_id", ""),
            "status": getattr(final_state, "status", "COMPLETED"),
            "errors": getattr(final_state, "errors", []),
        },
    )


async def run_offline_pipeline(
    input_path: Path | None,
    url: str | None,
    meeting_id: str,
    template: str = "meeting_minutes",
    context: str | None = None,
    num_speakers: int | None = None,
    denoise_level: int = 1,
    extract_frames: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_rec_"))

    if url:
        if progress_callback:
            await progress_callback("started", {"message": "正在解析并下载视频链接..."})
        parse_link(url)
        download_dir = work_dir / "download"
        download_dir.mkdir(exist_ok=True)

        try:
            logger.info(f"Downloading video from URL: {url}")
            downloaded_file = await asyncio.to_thread(download_video, url, download_dir)
            actual_path = Path(downloaded_file)
        except Exception as err:
            logger.warning(f"Failed to download video: {err}, falling back to audio download")
            try:
                downloaded_file = await asyncio.to_thread(download_audio, url, download_dir)
                actual_path = Path(downloaded_file)
            except Exception as audio_err:
                logger.error(f"Failed to download audio: {audio_err}")
                raise RuntimeError(f"无法下载视频或音频链接: {str(audio_err)}")
    elif input_path:
        actual_path = input_path
    else:
        raise ValueError("必须提供 input_path 或 url 中的一个")

    if progress_callback:
        await progress_callback("preprocess", {"message": "正在进行媒体预处理（提取音轨、降噪）..."})

    pre_result = await asyncio.to_thread(
        preprocess,
        input_files=[actual_path],
        work_dir=work_dir,
        denoise_level=denoise_level,
    )

    if progress_callback:
        await progress_callback("transcribe", {"message": "正在进行语音识别转录..."})

    language = await asyncio.to_thread(detect_language, pre_result.audio_path)
    transcript = await asyncio.to_thread(transcribe, pre_result.audio_path, language=language)

    if progress_callback:
        await progress_callback("diarize", {"message": "正在进行说话人声纹识别与对齐..."})

    if len(transcript.segments) > 0:
        diar_result = await asyncio.to_thread(
            diarize,
            audio_path=pre_result.audio_path,
            transcript=transcript,
            num_speakers=num_speakers,
        )
    else:
        diar_result = DiarizationResult(
            segments=[
                DiarizedSegment(segment.start, segment.end, segment.text, "Speaker 1")
                for segment in transcript.segments
            ],
            num_speakers=1,
            speakers=["Speaker 1"],
            language=language,
        )

    frames_result = []
    if extract_frames and pre_result.is_video and pre_result.video_path:
        if progress_callback:
            await progress_callback("keyframes", {"message": "正在提取关键帧（仅视频支持）..."})
        frames_dir = work_dir / "keyframes"
        frames_dir.mkdir(exist_ok=True)
        try:
            extracted_frames = await asyncio.to_thread(
                extract_keyframes,
                video_path=pre_result.video_path,
                output_dir=frames_dir,
                max_frames=10,
            )
            frames_result = align_frames_to_subtitles(extracted_frames, transcript)
        except Exception as frame_err:
            logger.error(f"Failed to extract/align keyframes: {frame_err}")

    if progress_callback:
        await progress_callback("agent_running", {"message": "AI 会议协同助理正在并行分析（纪要生成、待办提取、效率评估、跟进）..."})

    final_state = await run_meeting_pipeline(
        meeting_id=meeting_id,
        transcript_text=diar_result.transcript_with_speakers,
        transcript=diar_result,
        template=template,
        context=context,
    )

    outputs = _serialize_agent_outputs(final_state)
    return {
        "meeting_id": meeting_id,
        "status": getattr(final_state, "status", "COMPLETED"),
        "duration": pre_result.duration,
        "num_speakers": diar_result.num_speakers,
        "speakers": diar_result.speakers,
        "transcript": diar_result.full_text,
        "diarized_transcript": diar_result.transcript_with_speakers,
        "summary": outputs["summary"],
        "actions": outputs["actions"],
        "insights": outputs["insights"],
        "followup": outputs["followup"],
        "keyframes": [
            {
                "path": str(frame.path),
                "timestamp": frame.timestamp,
                "timestamp_str": frame.timestamp_str,
                "subtitle_text": frame.subtitle_text,
            }
            for frame in frames_result
        ],
        "errors": getattr(final_state, "errors", []),
    }
