# -*- coding: utf-8 -*-
"""
在线实时音频流处理与 Agent 事件推送流水线
"""
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
    """
    处理来自 WebSocket 实时录音的音频数据流。

    完整处理链路：音频 bytes -> 临时文件 -> 降噪 -> 语言检测 -> ASR 转录 ->
    说话人分离 -> LangGraph 多 Agent 协作分析。

    Args:
        audio_bytes: 实时录音的原始音频字节数据
        meeting_id: 会议唯一标识符，用于追踪本次会话
        denoise_level: 降噪强度等级，默认 1（轻度），取值 0-3
        num_speakers: 预设发言人数，若不提供则由系统自动检测

    Returns:
        tuple[final_state, diar_result, transcript_payload]：
        - final_state: LangGraph 工作流输出的完整状态（含四个 Agent 的分析结果）
        - diar_result: 说话人分离结果（包含分段的发言人和文本）
        - transcript_payload: ASR 转录结果的结构化载荷（用于 API 响应）
    """
    # Step 1: 将音频字节写入临时文件
    tmp_base = find_project_root() / "tmp_workspace"
    tmp_base.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_ws_", dir=str(tmp_base)))
    try:
        audio_file = work_dir / "input_audio.wav"
        audio_file.write_bytes(audio_bytes)

        # Step 2: 降噪预处理
        pre_result = await asyncio.to_thread(
            preprocess,
            input_files=[audio_file],
            work_dir=work_dir,
            denoise_level=denoise_level,
        )

        # Step 3: 检测音频语言（用于后续 ASR 模型选择）
        language = await asyncio.to_thread(detect_language, pre_result.audio_path)

        # Step 4: ASR 语音识别转录
        transcript = await asyncio.to_thread(transcribe, pre_result.audio_path, language=language)

        # Step 5: 说话人分离（若转录有结果则进行声纹识别，否则降级为单说话人模式）
        if len(transcript.segments) > 0:
            diar_result = await asyncio.to_thread(
                diarize,
                audio_path=pre_result.audio_path,
                transcript=transcript,
                num_speakers=num_speakers,
            )
        else:
            diar_result = create_fallback_diarization(transcript, language)

        # Step 6: 调用 LangGraph 多 Agent 工作流进行并行分析
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

        # Step 7: 组装 ASR 转录载荷用于 API 响应
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
    """
    将四个 Agent 的分析结果通过进度回调逐个向外层推送，最后推送完成事件。

    推送顺序：summary -> actions -> insights -> followup -> completed。
    上层（如 WebSocket）可据此实现实时进度展示。

    Args:
        final_state: 工作流最终状态对象
        emit: 进度回调函数，接收 (stage_name, data_dict)
    """
    # 此处是正确用法：将 Pydantic 对象序列化为 dict 推送给 WebSocket 客户端
    outputs = dump_outputs_for_json(final_state)

    # 依次推送四个 Agent 的输出
    for key in ("summary", "actions", "insights", "followup"):
        if outputs[key]:
            await emit(key, outputs[key])

    # 推送完成事件，包含会议 ID、最终状态和错误列表
    await emit(
        "completed",
        {
            "meeting_id": final_state.get("meeting_id", ""),
            "status": final_state.get("status", "COMPLETED"),
            "errors": final_state.get("errors", []),
        },
    )
