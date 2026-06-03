# -*- coding: utf-8 -*-
"""
原子化分析接口 — POST /api/v1/analyze

纯 JSON 分析接口：接受已转录文本，只运行分析 Agent（Summary/Action/Insight），
返回结构化小卡片。不涉及音视频处理、不触发渲染、不推送外部系统。

与 /api/v1/recording/process（全链路入口）是平行入口关系，永久共存。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from schemas import JobConfig, ChannelConfig
from services.integrations import create_llm_client, FeishuClient, JiraClient
from services.checkpoint_service import CheckpointService
from workflows.meeting_workflow import run_meeting_pipeline

router = APIRouter(prefix="/api/v1", tags=["analyze"])

# 持久化服务实例
_checkpoint = CheckpointService()


class AnalyzeRequest(BaseModel):
    """分析接口请求体"""
    transcript_text: str = Field(..., description="带发言人标记的格式化转录文本", min_length=1)
    meeting_id: str | None = Field(None, description="会议 ID，不传则自动生成")
    job_config: JobConfig = Field(default_factory=lambda: JobConfig(
        # 分析接口默认关闭渲染和分发（这是它与 /recording/process 的本质区别）
        enable_report_render=False,
        enable_mindmap=False,
        enable_delivery=False,
    ), description="流程控制配置（默认仅开启分析 Agent）")


class AnalyzeResponse(BaseModel):
    """分析接口响应体"""
    meeting_id: str
    summary: dict[str, Any] | None = None
    actions: dict[str, Any] | None = None
    insights: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


def _model_dump_if_needed(value: Any) -> Any:
    """如果值是 Pydantic 模型则序列化为 dict"""
    if value is not None and hasattr(value, "model_dump"):
        return value.model_dump()
    return value


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(request: AnalyzeRequest):
    """
    纯 JSON 分析接口 — 毫秒级返回结构化小卡片。

    只运行 LangGraph 分析 Agent，不涉及音视频处理、报告渲染和外部推送。
    产物自动持久化到 reports/{meeting_id}/checkpoint_analyze.json。
    """
    meeting_id = request.meeting_id or str(uuid.uuid4())[:12]

    # 强制关闭渲染和分发（analyze 接口的本质约束）
    job_config = request.job_config.model_copy(update={
        "enable_report_render": False,
        "enable_mindmap": False,
        "enable_delivery": False,
        "feishu": ChannelConfig(enabled=False),
        "jira": ChannelConfig(enabled=False),
    })

    try:
        llm_client = create_llm_client()
        jira_client = JiraClient()
        feishu_client = FeishuClient()

        final_state = await run_meeting_pipeline(
            meeting_id=meeting_id,
            transcript_text=request.transcript_text,
            llm_client=llm_client,
            jira_client=jira_client,
            feishu_client=feishu_client,
            job_config=job_config,
        )

        # 组装响应
        response_data = {
            "meeting_id": meeting_id,
            "summary": _model_dump_if_needed(final_state.get("summary")),
            "actions": _model_dump_if_needed(final_state.get("actions")),
            "insights": _model_dump_if_needed(final_state.get("insights")),
            "errors": final_state.get("errors", []),
        }

        # 持久化分析产物
        await _checkpoint.save(meeting_id, "analyze", response_data)

        return response_data

    except Exception as e:
        logger.exception(f"[AnalyzeEndpoint] 分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
