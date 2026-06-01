# -*- coding: utf-8 -*-
"""
用于会议录制音频/视频处理工作流的后台应用服务。

核心职责：
- 处理来自 WebSocket 实时录音的音频流
- 处理来自 API 的离线音视频文件（本地文件或在线链接）
- 统一调度 media_engine 媒体处理模块与 meeting_workflow 多 Agent 工作流
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
from services.integrations import create_llm_client, FeishuClient, JiraClient
from schemas import JobConfig
from services.checkpoint_service import CheckpointService

# 全局 Checkpoint 服务实例
_checkpoint = CheckpointService()


def _create_fallback_diarization(
    transcript: Any, language: str
) -> DiarizationResult:
    """当转录为空或无法进行声纹分离时，创建默认的单说话人分离结果。"""
    return DiarizationResult(
        segments=[
            DiarizedSegment(segment.start, segment.end, segment.text, "Speaker 1")
            for segment in transcript.segments
        ],
        num_speakers=1,
        speakers=["Speaker 1"],
        language=language,
    )


def parse_transcript_file(path: Path) -> DiarizationResult:
    import re
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    segments = []
    speakers = set()
    full_text_parts = []
    
    current_speaker = "Speaker 1"
    current_time_s = 0.0
    
    # 匹配 **Speaker 1** (00:00:00):
    pattern_header = re.compile(r"^\*\*(.*?)\*\*\s*\((\d+:\d+(?::\d+)?)\):")
    # 匹配 [Speaker 1] (00:00:00): 大家好
    pattern_bracket = re.compile(r"^\[(.*?)\]\s*\((\d+:\d+(?::\d+)?)\):\s*(.*)$")
    # 匹配 Speaker 1: 大家好
    pattern_colon = re.compile(r"^([^:\*]+):\s*(.*)$")
    
    def _parse_time(ts_str: str) -> float:
        parts = ts_str.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        except ValueError:
            pass
        return 0.0

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        
        # 1. 匹配标准段落头: **Speaker 1** (00:00:00):
        match_h = pattern_header.match(line_strip)
        if match_h:
            current_speaker = match_h.group(1).strip()
            current_time_s = _parse_time(match_h.group(2))
            speakers.add(current_speaker)
            continue
            
        # 2. 匹配中括号带时间戳: [Speaker 1] (00:00:00): 大家好
        match_b = pattern_bracket.match(line_strip)
        if match_b:
            spk = match_b.group(1).strip()
            ts = _parse_time(match_b.group(2))
            text = match_b.group(3).strip()
            speakers.add(spk)
            segments.append(DiarizedSegment(
                start=ts,
                end=ts + 5.0,
                text=text,
                speaker=spk
            ))
            full_text_parts.append(text)
            continue
            
        # 3. 匹配冒号分割: Speaker 1: 大家好
        match_c = pattern_colon.match(line_strip)
        if match_c:
            spk = match_c.group(1).strip()
            text = match_c.group(2).strip()
            if not spk.lower().startswith("http") and len(spk) < 30:
                speakers.add(spk)
                segments.append(DiarizedSegment(
                    start=current_time_s,
                    end=current_time_s + 5.0,
                    text=text,
                    speaker=spk
                ))
                full_text_parts.append(text)
                current_time_s += 5.0
                continue
        
        # 4. 普通缩进行或普通行
        text = line_strip
        segments.append(DiarizedSegment(
            start=current_time_s,
            end=current_time_s + 5.0,
            text=text,
            speaker=current_speaker
        ))
        full_text_parts.append(text)
        current_time_s += 5.0

    speakers.add(current_speaker)
    return DiarizationResult(
        segments=segments,
        num_speakers=len(speakers) or 1,
        speakers=sorted(list(speakers)) or ["Speaker 1"],
        language="zh",
    )


# 进度回调函数类型：接收 (stage: str, metadata: dict) 并返回 Awaitable[None]
ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def _model_dump_if_needed(value: Any) -> Any:
    """
    如果值是 Pydantic 模型（有 model_dump 方法），则序列化为 dict；否则直接返回原值。

    Args:
        value: 待检查的值，可能是 Pydantic 模型实例或其他类型

    Returns:
        序列化后的 dict 或原始值
    """
    if value is not None and hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _serialize_agent_outputs(final_state: dict[str, Any]) -> dict[str, Any]:
    """
    从工作流最终状态中提取并序列化四个 Agent 的输出结果。

    四个 Agent 分别为：summary（摘要）、actions（行动项）、insights（洞察）、followup（跟进）。

    Args:
        final_state: meeting_workflow 完成后返回的最终状态字典

    Returns:
        包含四个 Agent 输出的字典，所有 Pydantic 模型已被序列化为 dict
    """
    return {
        "summary": _model_dump_if_needed(final_state.get("summary")),
        "actions": _model_dump_if_needed(final_state.get("actions")),
        "insights": _model_dump_if_needed(final_state.get("insights")),
        "followup": _model_dump_if_needed(final_state.get("followup")),
    }


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
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_ws_"))
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
        diar_result = _create_fallback_diarization(transcript, language)

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


async def emit_agent_events(final_state: Any, emit: ProgressCallback) -> None:
    """
    将四个 Agent 的分析结果通过进度回调逐个向外层推送，最后推送完成事件。

    推送顺序：summary -> actions -> insights -> followup -> completed。
    上层（如 WebSocket）可据此实现实时进度展示。

    Args:
        final_state: 工作流最终状态对象
        emit: 进度回调函数，接收 (stage_name, data_dict)
    """
    outputs = _serialize_agent_outputs(final_state)

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


async def run_offline_pipeline(
    input_path: Path | None,
    url: str | None,
    meeting_id: str,
    context: str | None = None,
    num_speakers: int | None = None,
    denoise_level: int = 1,
    extract_frames: bool = True,
    progress_callback: ProgressCallback | None = None,
    job_config: JobConfig | None = None,
) -> dict[str, Any]:
    """
    离线音视频处理主流水线（API 层调用的核心入口）。

    支持两种输入源：
    - 在线链接（B站、YouTube 等）：自动下载后处理
    - 本地文件：直接处理

    完整流水线：
    下载/读取 -> 预处理（降噪、提取音轨）-> 语言检测 -> ASR 转录 ->
    说话人分离 -> 关键帧提取（仅视频）-> LangGraph 多 Agent 分析 ->
    报告渲染（Markdown/PDF/HTML/思维导图）

    Args:
        input_path: 本地音视频文件路径（与 url 二选一）
        url: 在线视频链接（与 input_path 二选一）
        meeting_id: 会议唯一标识符
        context: 补充上下文描述，帮助 AI 更准确理解内容
        num_speakers: 预设发言人数，不提供则自动检测
        denoise_level: 降噪强度，取值 0-3，默认 1
        extract_frames: 是否提取关键帧（仅对视频生效），默认 True
        progress_callback: 可选的进度回调函数，用于 SSE 实时推送处理阶段

    Returns:
        包含完整处理结果的字典：
        - meeting_id, title, status, duration, num_speakers, speakers
        - transcript: 原始转录文本
        - diarized_transcript: 带说话人标签的转录文本
        - content: 渲染后的 Markdown 报告正文
        - output_files: 各格式输出文件路径（markdown/pdf/html/mindmap）
        - summary/actions/insights/followup: 四个 Agent 的结构化输出
        - keyframes: 关键帧列表（含时间戳和对应字幕）
        - errors: 处理过程中的错误列表
    """
    # Step 1: 创建临时工作目录
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_rec_"))

    # Step 2: 确定输入来源（在线链接 或 本地文件）
    if url:
        # 在线链接：先解析，再下载音视频
        if progress_callback:
            await progress_callback("started", {"message": "正在解析并下载视频链接..."})
        parsed = parse_link(url)
        logger.info(f"检测到链接平台: {parsed.platform.value}, 类型: {parsed.link_type.value}")
        download_dir = work_dir / "download"
        download_dir.mkdir(exist_ok=True)

        try:
            # 优先尝试下载完整视频
            logger.info(f"Downloading video from URL: {url}")
            downloaded_file = await asyncio.to_thread(download_video, url, download_dir)
            actual_path = Path(downloaded_file)
        except Exception as err:
            # 视频下载失败时降级为仅下载音频（YouTube Reject 等场景）
            logger.warning(f"Failed to download video: {err}, falling back to audio download")
            try:
                downloaded_file = await asyncio.to_thread(download_audio, url, download_dir)
                actual_path = Path(downloaded_file)
            except Exception as audio_err:
                # 音视频下载均失败，抛出明确错误
                logger.error(f"Failed to download audio: {audio_err}")
                raise RuntimeError(f"无法下载视频或音频链接: {str(audio_err)}")
    elif input_path:
        # 本地文件：直接使用指定路径
        actual_path = input_path
    else:
        raise ValueError("必须提供 input_path 或 url 中的一个")

    # 检测是否为已转录文本文件输入
    is_transcript_input = False
    if actual_path and actual_path.suffix.lower() == ".txt":
        is_transcript_input = True

    if not is_transcript_input:
        # Step 3: 媒体预处理（降噪、提取音轨、获取视频元信息）
        if progress_callback:
            await progress_callback("preprocess", {"message": "正在进行媒体预处理（提取音轨、降噪）..."})

        pre_result = await asyncio.to_thread(
            preprocess,
            input_files=[actual_path],
            work_dir=work_dir,
            denoise_level=denoise_level,
        )

        # Step 4: 语言检测（用于 ASR 模型选择）
        if progress_callback:
            await progress_callback("transcribe", {"message": "正在进行语音识别转录..."})

        language = await asyncio.to_thread(detect_language, pre_result.audio_path)

        # Step 5: ASR 语音识别转录
        import time
        start_time = time.time()
        transcribe_task = asyncio.create_task(asyncio.to_thread(transcribe, pre_result.audio_path, language=language))
        
        while not transcribe_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(transcribe_task), timeout=5.0)
            except asyncio.TimeoutError:
                elapsed = int(time.time() - start_time)
                if progress_callback:
                    await progress_callback("transcribe", {"message": f"正在进行语音识别转录... (已耗时 {elapsed}s，大文件请耐心等待)"})
                    
        transcript = transcribe_task.result()

        # Step 6: 说话人分离（声纹识别 + 文本对齐）
        if progress_callback:
            await progress_callback("diarize", {"message": "正在进行说话人声纹识别与对齐..."})

        if len(transcript.segments) > 0:
            diar_start_time = time.time()
            diar_task = asyncio.create_task(asyncio.to_thread(
                diarize,
                audio_path=pre_result.audio_path,
                transcript=transcript,
                num_speakers=num_speakers,
            ))
            while not diar_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(diar_task), timeout=5.0)
                except asyncio.TimeoutError:
                    elapsed = int(time.time() - diar_start_time)
                    if progress_callback:
                        await progress_callback("diarize", {"message": f"正在进行说话人声纹识别与对齐... (已耗时 {elapsed}s，大文件请耐心等待)"})
            diar_result = diar_task.result()
        else:
            diar_result = _create_fallback_diarization(transcript, language)

        # 【Checkpoint】阶段性保存产物（在此刻先将转录文本落盘，防止后续流程报错丢失数据）
        try:
            await _checkpoint.save(meeting_id, "transcribe", {
                "transcript_text": diar_result.transcript_with_speakers,
                "num_speakers": diar_result.num_speakers,
                "speakers": diar_result.speakers,
                "language": language if 'language' in dir() else "zh",
            })
        except Exception as tx_err:
            logger.error(f"[ApplicationService] Failed to save transcribe checkpoint: {tx_err}")

        try:
            from services import _find_project_root
            reports_dir = _find_project_root() / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            intermediate_tx_path = reports_dir / f"{meeting_id}_transcript.txt"
            intermediate_tx_path.write_text(diar_result.transcript_with_speakers, encoding="utf-8")
            logger.info(f"[ApplicationService] Saved intermediate transcript text to {intermediate_tx_path}")
        except Exception as tx_err:
            logger.error(f"[ApplicationService] Failed to save intermediate transcript: {tx_err}")

        # Step 7: 关键帧提取与字幕对齐（仅视频模式生效）
        frames_result = []
        if extract_frames and pre_result.is_video and pre_result.video_path:
            if progress_callback:
                await progress_callback("keyframes", {"message": "正在提取关键帧（仅视频支持）..."})
            frames_dir = work_dir / "keyframes"
            frames_dir.mkdir(exist_ok=True)
            try:
                # 提取关键帧后，将每帧与最近的字幕段落对齐（用于报告中插入截图）
                extracted_frames = await asyncio.to_thread(
                    extract_keyframes,
                    video_path=pre_result.video_path,
                    output_dir=frames_dir,
                    max_frames=10,
                )
                frames_result = align_frames_to_subtitles(extracted_frames, transcript)
            except Exception as frame_err:
                # 关键帧提取失败不影响主流程，仅记录日志
                logger.error(f"Failed to extract/align keyframes: {frame_err}")
    else:
        # 直接解析文本
        if progress_callback:
            await progress_callback("transcribe", {"message": "检测到转录文本，正在进行解析..."})
        diar_result = parse_transcript_file(actual_path)
        frames_result = []
        # 构建一个 Dummy 预处理结果，因为文本输入没有真实的音视频
        class DummyPreResult:
            duration = diar_result.duration_seconds
            is_video = False
            video_path = None
        pre_result = DummyPreResult()

    # Step 8: LangGraph 多 Agent 并行分析
    if progress_callback:
        await progress_callback("agent_running", {"message": "AI 会议协同助理正在并行分析（纪要生成、待办提取、效率评估、跟进）..."})

    # 确保 job_config 有值
    if job_config is None:
        job_config = JobConfig()

    llm_client = create_llm_client()
    jira_client = JiraClient()
    feishu_client = FeishuClient()

    final_state = await run_meeting_pipeline(
        meeting_id=meeting_id,
        transcript_text=diar_result.transcript_with_speakers,
        transcript=diar_result,
        keyframes=frames_result,
        llm_client=llm_client,
        jira_client=jira_client,
        feishu_client=feishu_client,
        job_config=job_config,
    )

    # Step 9: 组装输出结果
    outputs = _serialize_agent_outputs(final_state)

    # 从 followup 产物中读取渲染后的 Markdown 报告正文
    content = ""
    output_files = {}
    followup_data = outputs.get("followup")
    if followup_data:
        artifacts = followup_data.get("artifacts")
        if artifacts:
            # 读取 Markdown 文件内容作为 API 响应正文
            md_path_str = artifacts.get("markdown_path")
            if md_path_str:
                md_path = Path(md_path_str)
                if md_path.exists():
                    try:
                        content = md_path.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.error(f"Failed to read generated markdown report: {e}")

            # 将各格式产物路径映射到 output_files
            for fmt, key in [
                ("markdown", "markdown_path"),
                ("pdf", "pdf_path"),
                ("html", "html_path"),
                ("mindmap", "mindmap_path")
            ]:
                path_str = artifacts.get(key)
                if path_str:
                    output_files[fmt] = path_str

    # 额外将转写文本写回为 reports 中的文本文件供下次复用，并在有标题时加上标题
    try:
        from services import _find_project_root
        reports_dir = _find_project_root() / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        summary_title = ""
        if outputs.get("summary"):
            summary_title = outputs["summary"].get("title", "")
            
        import re
        safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', summary_title).strip().strip("_") if summary_title else ""
        safe_title = safe_title[:50].strip()
        
        filename_base = f"{meeting_id}_{safe_title}" if safe_title else meeting_id
        final_tx_path = reports_dir / f"{filename_base}_transcript.txt"
        
        if not is_transcript_input:
            # 如果是刚跑出的任务，中间文件名为无标题版本
            intermediate_tx_path = reports_dir / f"{meeting_id}_transcript.txt"
            if intermediate_tx_path.exists():
                if final_tx_path != intermediate_tx_path:
                    # 将中间文件重命名为包含标题的新名字
                    import shutil
                    shutil.move(str(intermediate_tx_path), str(final_tx_path))
            else:
                final_tx_path.write_text(diar_result.transcript_with_speakers, encoding="utf-8")
            
            output_files["transcript"] = str(final_tx_path)
            logger.info(f"[ApplicationService] Final transcript text available at {final_tx_path}")
        else:
            # 如果输入本身就是 transcript 文件，则不再写入套娃复印本，直接沿用原路径
            output_files["transcript"] = str(actual_path)
            logger.info(f"[ApplicationService] Reused original transcript text from {actual_path}")
            
    except Exception as tx_err:
        logger.error(f"[ApplicationService] Failed to finalize transcript text file: {tx_err}")

    # 标题优先使用 Summary Agent 生成的主题，否则使用默认值
    summary_title = ""
    if outputs.get("summary"):
        summary_title = outputs["summary"].get("title", "")
    title = summary_title or f"会议报告 - {meeting_id}"

    # Step 10: 组装完整响应结构
    final_result = {
        "meeting_id": meeting_id,
        "title": title,
        "status": final_state.get("status", "COMPLETED"),
        "duration": pre_result.duration,
        "num_speakers": diar_result.num_speakers,
        "speakers": diar_result.speakers,
        "transcript": diar_result.full_text,
        "diarized_transcript": diar_result.transcript_with_speakers,
        "content": content,
        "output_files": output_files,
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
        "errors": final_state.get("errors", []),
    }

    # 【Checkpoint】持久化最终完整结果
    try:
        await _checkpoint.save_final(meeting_id, final_result)
    except Exception as e:
        logger.error(f"[ApplicationService] Failed to save final checkpoint: {e}")

    return final_result
