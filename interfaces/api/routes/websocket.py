# -*- coding: utf-8 -*-
"""
WebSocket Routes
- 提供 /ws/meeting/{meeting_id} 实时录音与结果流式推送接口
- 接收音频二进制帧并在收到控制命令后执行完整的多 Agent 缝合流程
"""

from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from services.pipeline import emit_agent_events, process_audio_capture
from services.media_engine import DiarizationResult, DiarizedSegment
from workflows.meeting_workflow import run_meeting_pipeline

router = APIRouter(tags=["websocket"])

# 活跃的连接池
active_connections: dict[str, WebSocket] = {}


async def _send_agent_results(websocket: WebSocket, final_state) -> None:
    async def sender(event_type: str, payload: dict) -> None:
        await websocket.send_json({"type": event_type, "data": payload})

    await emit_agent_events(final_state, sender)


def _generate_demo_transcript() -> DiarizationResult:
    """生成演示说话人分割结果"""
    segments = [
        DiarizedSegment(start=0.0, end=8.5, text="好的，我们开始今天的Q3预算评审会议。首先请李明汇报一下目前的预算执行情况。", speaker="张总"),
        DiarizedSegment(start=9.0, end=16.2, text="好的张总。截至目前，Q2预算执行率为87%，其中研发投入占比最大，达到42%。", speaker="李明"),
        DiarizedSegment(start=16.5, end=23.1, text="Q3我们计划将预算上调15%，主要增加在AI基础设施 and 人才招聘方面。", speaker="李明"),
        DiarizedSegment(start=23.5, end=31.0, text="关于人才招聘，我建议我们重点招聘3名高级算法工程师，预算大概在每人年薪80万左右。", speaker="王芳"),
        DiarizedSegment(start=31.5, end=38.2, text="可以。李明你来负责整理Q3的详细预算方案，下周五之前提交给我审批。", speaker="张总"),
        DiarizedSegment(start=38.5, end=46.0, text="王芳负责拟定招聘JD，本周三前完成。另外，赵伟跟进一下服务器采购的事情。", speaker="张总"),
        DiarizedSegment(start=46.5, end=52.8, text="收到，我这边已经在对比几家供应商了，预计下周一可以给出采购方案。", speaker="赵伟"),
        DiarizedSegment(start=53.0, end=59.5, text="好的，那今天的会议就到这里。各位辛苦了，请大家按时完成各自的任务。", speaker="张总"),
    ]
    return DiarizationResult(
        segments=segments,
        num_speakers=4,
        speakers=["张总", "李明", "王芳", "赵伟"],
        language="zh"
    )


@router.websocket("/ws/meeting/{meeting_id}")
async def websocket_meeting(websocket: WebSocket, meeting_id: str):
    """
    实时音频输入流和多 Agent 处理推送 WebSocket 接口
    """
    await websocket.accept()
    active_connections[meeting_id] = websocket
    audio_buffer = bytearray()

    logger.info(f"WebSocket 客户端已连接: {meeting_id}")

    try:
        await websocket.send_json({
            "type": "connected",
            "meeting_id": meeting_id,
            "message": "会议助手已连接，发送音频数据开始录制",
        })

        while True:
            data = await websocket.receive()

            if "bytes" in data and data["bytes"]:
                # 收到音频二进制片段
                audio_buffer.extend(data["bytes"])
                await websocket.send_json({
                    "type": "recording",
                    "buffer_size": len(audio_buffer),
                })

            elif "text" in data and data["text"]:
                # 收到 JSON 控制报文
                message = json.loads(data["text"])
                msg_type = message.get("type", "")

                if msg_type == "stop":
                    await websocket.send_json({
                        "type": "processing",
                        "message": "正在处理音频，请稍候...",
                    })

                    if not audio_buffer:
                        await websocket.send_json({
                            "type": "error",
                            "message": "未收到音频数据，无法开始处理",
                        })
                        continue

                    try:
                        final_state, diar_result, transcript_payload = await process_audio_capture(
                            audio_bytes=bytes(audio_buffer),
                            meeting_id=meeting_id,
                            denoise_level=1,
                        )
                        await websocket.send_json({
                            "type": "transcript",
                            "data": transcript_payload,
                        })
                        await websocket.send_json({
                            "type": "diarization",
                            "data": {
                                "transcript": diar_result.full_text,
                                "diarized_transcript": diar_result.transcript_with_speakers,
                                "num_speakers": diar_result.num_speakers,
                                "speakers": diar_result.speakers
                            }
                        })
                        await _send_agent_results(websocket, final_state)

                    except Exception as pipeline_err:
                        logger.exception("WebSocket 处理音频数据时发生异常")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"处理音频出错: {str(pipeline_err)}",
                        })

                    finally:
                        audio_buffer.clear()

                elif msg_type == "demo":
                    # 运行演示/测试模式
                    await websocket.send_json({
                        "type": "processing",
                        "message": "正在运行演示模式...",
                    })

                    diar_result = _generate_demo_transcript()

                    # 发送 Mock 转写和说话人结果
                    await websocket.send_json({
                        "type": "diarization",
                        "data": {
                            "transcript": diar_result.full_text,
                            "diarized_transcript": diar_result.transcript_with_speakers,
                            "num_speakers": diar_result.num_speakers,
                            "speakers": diar_result.speakers
                        }
                    })

                    # 调用 LangGraph 多 Agent 状态机
                    final_state = await run_meeting_pipeline(
                        meeting_id=meeting_id,
                        transcript_text=diar_result.transcript_with_speakers,
                        transcript=diar_result,
                    )
                    await _send_agent_results(websocket, final_state)

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket 客户端已断开: {meeting_id}")
    except Exception as e:
        logger.exception(f"会议 {meeting_id} 的 WebSocket 连接发生异常")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass
    finally:
        active_connections.pop(meeting_id, None)
