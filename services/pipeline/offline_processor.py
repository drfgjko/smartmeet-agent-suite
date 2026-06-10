
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
from services.core.checkpoint_service import CheckpointService
from utils import find_project_root, dump_outputs_for_json, create_fallback_diarization, parse_transcript_file
from schemas import SummaryOutput, ActionOutput, InsightOutput

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

    from utils import get_tmp_dir
    tmp_base = get_tmp_dir()
    work_dir = Path(tempfile.mkdtemp(prefix="smartmeet_rec_", dir=str(tmp_base)))
    try:

        if url:

            if progress_callback:
                await progress_callback("started", {"message": "正在解析并下载视频链接..."})
            parsed = parse_link(url)
            logger.info(f"检测到链接平台: {parsed.platform.value}, 类型: {parsed.link_type.value}")
            download_dir = work_dir / "download"
            download_dir.mkdir(exist_ok=True)

            try:

                logger.info(f"正在从 URL 下载视频: {url} (最高限制为 480P/720P 以优化带宽)")

                quality_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
                downloaded_file = await asyncio.to_thread(download_video, url, download_dir, quality_str)
                actual_path = Path(downloaded_file)
            except Exception as err:

                logger.warning(f"下载视频失败: {err}，正在降级为仅下载音频")
                try:
                    downloaded_file = await asyncio.to_thread(download_audio, url, download_dir)
                    actual_path = Path(downloaded_file)
                except Exception as audio_err:

                    logger.error(f"下载音频失败: {audio_err}")
                    raise RuntimeError(f"无法下载视频或音频链接: {str(audio_err)}")
        elif input_path:

            actual_path = input_path
        else:
            raise ValueError("必须提供 input_path 或 url 中的一个")

        is_transcript_input = False
        if actual_path and actual_path.suffix.lower() == ".txt":
            is_transcript_input = True

        if not is_transcript_input:

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

            language = await detect_language(pre_result.audio_path)

            import time
            start_time = time.time()
            transcribe_task = asyncio.create_task(transcribe(pre_result.audio_path, language=language))

            while not transcribe_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(transcribe_task), timeout=5.0)
                except asyncio.TimeoutError:
                    elapsed = int(time.time() - start_time)
                    if progress_callback:
                        await progress_callback("transcribe", {"message": f"正在进行语音识别转录... (已耗时 {elapsed}s，大文件请耐心等待)"})

            transcript = transcribe_task.result()

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
                from utils import get_reports_dir
                reports_dir = get_reports_dir() / meeting_id
                intermediate_tx_path = reports_dir / f"{meeting_id}_transcript.txt"
                intermediate_tx_path.write_text(diar_result.transcript_with_speakers, encoding="utf-8")
                logger.info(f"[ApplicationService] 已保存中间转录文本至 {intermediate_tx_path}")
            except Exception as tx_err:
                logger.error(f"[ApplicationService] 保存中间转录文本失败: {tx_err}")

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

                    frames_result = align_frames_to_subtitles(extracted_frames, transcript)
                except Exception as frame_err:

                    logger.error(f"提取/对齐关键帧失败: {frame_err}")
        else:

            if progress_callback:
                await progress_callback("transcribe", {"message": "检测到转录文本，正在进行解析..."})
            diar_result = parse_transcript_file(actual_path)
            frames_result = []

            class DummyPreResult:
                duration = diar_result.duration_seconds
                is_video = False
                video_path = None
            pre_result = DummyPreResult()

        if progress_callback:
            await progress_callback("agent_running", {"message": "AI 会议协同助理正在并行分析（纪要生成、待办提取、效率评估、跟进）..."})

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

        summary: SummaryOutput | None = final_state.get("summary")
        actions: ActionOutput | None = final_state.get("actions")
        insights: InsightOutput | None = final_state.get("insights")

        from services import ReportComposer, ReportRenderer, MindMapService, ReportDelivery

        md_path = None
        pdf_path = None
        html_path = None
        pdf_generated = False
        mindmap_path = None
        mindmap_html_path = None
        mindmap_generated = False
        final_report_md = ""

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
            title = summary.title if summary else None
            md_path, pdf_path, html_path, pdf_generated = await renderer.render_report(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                kf_objects=kf_objects,
                title=title,
            )

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
            title = summary.title if summary else None
            mindmap_path, mindmap_html_path, mindmap_generated = await mindmap_service.generate_and_save_mindmap(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                title=title,
            )

        if job_config.enable_delivery:
            delivery = ReportDelivery(feishu_client=feishu_client, jira_client=jira_client)
            await delivery.deliver_report(
                meeting_id=meeting_id,
                summary=summary or SummaryOutput(),
                actions=actions or ActionOutput(),
                insights=insights or InsightOutput(),
                pdf_path=pdf_path,
                pdf_generated=pdf_generated,
                mindmap_path=mindmap_path,
                mindmap_generated=mindmap_generated,
                feishu_config=job_config.feishu,
                jira_config=job_config.jira,
            )

        if job_config.enable_task_sync and actions:
            from services.integrations import sync_actions_to_external
            await sync_actions_to_external(
                items=actions.action_items,
                meeting_id=meeting_id,
                jira_client=jira_client,
                feishu_client=feishu_client,
                jira_config=job_config.jira,
                feishu_config=job_config.feishu,
            )

        content = ""
        output_files = {}

        if not is_transcript_input and hasattr(pre_result, 'audio_path') and pre_result.audio_path and pre_result.audio_path.exists():
            try:
                import shutil
                from utils import get_reports_dir
                reports_dir = get_reports_dir() / meeting_id
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
        if mindmap_generated and mindmap_html_path:
            output_files["mindmap_html"] = str(mindmap_html_path)

        try:
            from utils import get_reports_dir
            reports_dir = get_reports_dir() / meeting_id

            summary_title = summary.title if summary else ""

            import re
            safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', summary_title).strip().strip("_") if summary_title else ""
            safe_title = safe_title[:50].strip()

            filename_base = f"{meeting_id}_{safe_title}" if safe_title else meeting_id
            final_tx_path = reports_dir / f"{filename_base}_transcript.txt"

            if not is_transcript_input:

                intermediate_tx_path = reports_dir / f"{meeting_id}_transcript.txt"
                if intermediate_tx_path.exists():
                    if final_tx_path != intermediate_tx_path:

                        import shutil
                        shutil.move(str(intermediate_tx_path), str(final_tx_path))
                else:
                    final_tx_path.write_text(diar_result.transcript_with_speakers, encoding="utf-8")

                output_files["transcript"] = str(final_tx_path)
                logger.info(f"[ApplicationService] 最终转录文本已保存至 {final_tx_path}")
            else:

                output_files["transcript"] = str(actual_path)
                logger.info(f"[ApplicationService] 复用了原始转录文本: {actual_path}")

        except Exception as tx_err:
            logger.error(f"[ApplicationService] 最终生成转录文本文件失败: {tx_err}")

        title = (summary.title if summary else "") or f"会议报告 - {meeting_id}"

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

            "summary": summary.model_dump() if summary else {},
            "actions": actions.model_dump() if actions else {},
            "insights": insights.model_dump() if insights else {},
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

        try:
            await _checkpoint.save_final(meeting_id, final_result)

            _checkpoint.cleanup_checkpoints(meeting_id)
        except Exception as e:
            logger.error(f"[ApplicationService] 保存最终检查点失败: {e}")

    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(f"[ApplicationService] 已自动清理临时工作目录: {work_dir}")

    return final_result

