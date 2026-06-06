# -*- coding: utf-8 -*-
"""
离线音视频文件/链接处理流水线
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from services.media_engine import (
    align_frames_to_subtitles,
    detect_language,
    diarize,
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
from utils import find_project_root, serialize_agent_outputs, create_fallback_diarization, parse_transcript_file

_checkpoint = CheckpointService()
ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

async def run_offline_pipeline(
    input_path: Path | None,
    url: str | None,
    meeting_id: str,
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
    tmp_base = find_project_root() / "tmp_workspace"
    tmp_base.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_rec_", dir=str(tmp_base)))
    try:

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
                logger.info(f"正在从 URL 下载视频: {url}")
                downloaded_file = await asyncio.to_thread(download_video, url, download_dir)
                actual_path = Path(downloaded_file)
            except Exception as err:
                # 视频下载失败时降级为仅下载音频（YouTube Reject 等场景）
                logger.warning(f"下载视频失败: {err}，正在降级为仅下载音频")
                try:
                    downloaded_file = await asyncio.to_thread(download_audio, url, download_dir)
                    actual_path = Path(downloaded_file)
                except Exception as audio_err:
                    # 音视频下载均失败，抛出明确错误
                    logger.error(f"下载音频失败: {audio_err}")
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
                diar_result = create_fallback_diarization(transcript, language)

            # 【Checkpoint】阶段性保存产物（在此刻先将转录文本落盘，防止后续流程报错丢失数据）
            try:
                await _checkpoint.save(meeting_id, "transcribe", {
                    "transcript_text": diar_result.transcript_with_speakers,
                    "num_speakers": diar_result.num_speakers,
                    "speakers": diar_result.speakers,
                    "language": language if 'language' in dir() else "zh",
                })
            except Exception as tx_err:
                logger.error(f"[ApplicationService] 保存转录检查点失败: {tx_err}")

            try:
                reports_dir = find_project_root() / "reports" / meeting_id
                reports_dir.mkdir(parents=True, exist_ok=True)
                intermediate_tx_path = reports_dir / f"{meeting_id}_transcript.txt"
                intermediate_tx_path.write_text(diar_result.transcript_with_speakers, encoding="utf-8")
                logger.info(f"[ApplicationService] 已保存中间转录文本至 {intermediate_tx_path}")
            except Exception as tx_err:
                logger.error(f"[ApplicationService] 保存中间转录文本失败: {tx_err}")

            # Step 7: 关键帧提取与字幕对齐（仅视频模式生效）
            frames_result = []
            if extract_frames and pre_result.is_video and pre_result.video_path:
                if progress_callback:
                    await progress_callback("keyframes", {"message": "正在提取关键帧（仅视频支持）..."})
                frames_dir = work_dir / "keyframes"
                frames_dir.mkdir(exist_ok=True)
                try:
                    import time
                    kf_start_time = time.time()
                    kf_task = asyncio.create_task(asyncio.to_thread(
                        extract_keyframes,
                        video_path=pre_result.video_path,
                        output_dir=frames_dir,
                        max_frames=10,
                    ))
                    while not kf_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(kf_task), timeout=5.0)
                        except asyncio.TimeoutError:
                            elapsed = int(time.time() - kf_start_time)
                            if progress_callback:
                                await progress_callback("keyframes", {"message": f"正在提取关键帧（仅视频支持）... (已耗时 {elapsed}s，大文件请耐心等待)"})
                    
                    extracted_frames = kf_task.result()
                    # 提取关键帧后，将每帧与最近的字幕段落对齐（用于报告中插入截图）
                    frames_result = align_frames_to_subtitles(extracted_frames, transcript)
                except Exception as frame_err:
                    # 关键帧提取失败不影响主流程，仅记录日志
                    logger.error(f"提取/对齐关键帧失败: {frame_err}")
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
            job_config=job_config,
        )

        # Step 9: 组装输出结果
        outputs = serialize_agent_outputs(final_state)

        # ── 图后处理：渲染 + 自动分发报告 ──
        from services import ReportComposer, ReportRenderer, MindMapService, ReportDelivery
        from schemas import FollowUpArtifacts

        md_path = None
        pdf_path = None
        html_path = None
        pdf_generated = False
        mindmap_path = None
        mindmap_generated = False
        final_report_md = ""
        
        summary = outputs.get("summary")
        actions = outputs.get("actions")
        insights = outputs.get("insights")

        # 1. 报告渲染
        if job_config.enable_report_render:
            composer = ReportComposer(llm_client=llm_client)
            renderer = ReportRenderer(llm_client=llm_client)
            final_report_md, kf_objects = await composer.compose_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                keyframes=frames_result,
            )
            title = summary.get("title") if summary else None
            md_path, pdf_path, html_path, pdf_generated = await renderer.render_report(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                kf_objects=kf_objects,
                title=title,
            )

        # 2. 思维导图
        if job_config.enable_mindmap:
            mindmap_service = MindMapService(llm_client=llm_client)
            if not final_report_md:
                composer = ReportComposer(llm_client=llm_client)
                final_report_md, _ = await composer.compose_report(
                    meeting_id=meeting_id,
                    summary=summary,
                    actions=actions,
                    insights=insights,
                    keyframes=frames_result,
                )
            title = summary.get("title") if summary else None
            mindmap_path, mindmap_generated = await mindmap_service.generate_and_save_mindmap(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                title=title,
            )

        # 3. 自动分发报告（仅卡片/PDF/导图，不含任务同步）
        if job_config.enable_delivery:
            delivery = ReportDelivery(feishu_client=feishu_client, jira_client=jira_client)
            # 需要把 dict 转换为 Pydantic 对象，或者依赖 Pydantic 自动转型
            from schemas import SummaryOutput, ActionOutput, InsightOutput
            await delivery.deliver_report(
                meeting_id=meeting_id,
                summary=SummaryOutput(**summary) if summary else SummaryOutput(),
                actions=ActionOutput(**actions) if actions else ActionOutput(),
                insights=InsightOutput(**insights) if insights else InsightOutput(),
                pdf_path=pdf_path,
                pdf_generated=pdf_generated,
                mindmap_path=mindmap_path,
                mindmap_generated=mindmap_generated,
                feishu_config=job_config.feishu,
                jira_config=job_config.jira,
            )

        # 4. 任务同步（创建飞书待办 / Jira Issue）
        if job_config.enable_task_sync and actions:
            from services.integrations import sync_actions_to_external
            from schemas import ActionOutput
            action_obj = ActionOutput(**actions) if isinstance(actions, dict) else actions
            await sync_actions_to_external(
                items=action_obj.action_items,
                meeting_id=meeting_id,
                jira_client=jira_client,
                feishu_client=feishu_client,
                jira_config=job_config.jira,
                feishu_config=job_config.feishu,
            )

        # 将生成的路径整理到 output_files 和 content 中
        content = ""
        output_files = {}

        # 持久化音频文件
        if not is_transcript_input and hasattr(pre_result, 'audio_path') and pre_result.audio_path and pre_result.audio_path.exists():
            try:
                import shutil
                reports_dir = find_project_root() / "reports" / meeting_id
                reports_dir.mkdir(parents=True, exist_ok=True)
                audio_dest = reports_dir / "audio.wav"
                shutil.copy2(str(pre_result.audio_path), str(audio_dest))
                output_files["audio"] = str(audio_dest)
            except Exception as e:
                logger.error(f"持久化音频文件失败: {e}")
        if md_path and md_path.exists():
            try:
                content = md_path.read_text(encoding="utf-8")
                output_files["markdown"] = str(md_path)
            except Exception as e:
                logger.error(f"读取生成的 Markdown 报告失败: {e}")
        if pdf_generated and pdf_path:
            output_files["pdf"] = str(pdf_path)
        if html_path:
            output_files["html"] = str(html_path)
        if mindmap_generated and mindmap_path:
            output_files["mindmap"] = str(mindmap_path)

        # 额外将转写文本写回为 reports 中的文本文件供下次复用，并在有标题时加上标题
        try:
            reports_dir = find_project_root() / "reports" / meeting_id
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
                logger.info(f"[ApplicationService] 最终转录文本已保存至 {final_tx_path}")
            else:
                # 如果输入本身就是 transcript 文件，则不再写入套娃复印本，直接沿用原路径
                output_files["transcript"] = str(actual_path)
                logger.info(f"[ApplicationService] 复用了原始转录文本: {actual_path}")
            
        except Exception as tx_err:
            logger.error(f"[ApplicationService] 最终生成转录文本文件失败: {tx_err}")

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
            "summary": outputs.get("summary", {}),
            "actions": outputs.get("actions", {}),
            "insights": outputs.get("insights", {}),
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
            # 成功保存最终结果后，清理掉冗余的中间过程文件
            _checkpoint.cleanup_checkpoints(meeting_id)
        except Exception as e:
            logger.error(f"[ApplicationService] 保存最终检查点失败: {e}")

    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(f"[ApplicationService] 已自动清理临时工作目录: {work_dir}")

    return final_result

