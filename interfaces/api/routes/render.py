# -*- coding: utf-8 -*-
"""
原子化渲染接口 — POST /api/v1/render

接受分析 Agent 的 JSON 输出，专门拉起渲染集群生成 Markdown/PDF/HTML/思维导图报告，
并按 JobConfig 配置执行外部分发（飞书/Jira/Webhook）。

与 /api/v1/analyze 配合使用：先调 analyze 拿到数据展示卡片 → 用户确认后调 render 生成报告。
与 /api/v1/recording/process（全链路入口）是平行入口关系，永久共存。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from schemas import (
    JobConfig,
    SummaryOutput,
    ActionOutput,
    InsightOutput,
    FollowUpArtifacts,
    DeliveryResult,
)
from services import ReportComposer, ReportRenderer, MindMapService, ReportDelivery
from services.delivery import WebhookService
from services.integrations import create_llm_client, FeishuClient, JiraClient
from services.core.checkpoint_service import CheckpointService

router = APIRouter(prefix="/api/v1", tags=["render"])

# 持久化服务实例
_checkpoint = CheckpointService()


class RenderRequest(BaseModel):
    """渲染接口请求体 — 接受分析 Agent 的完整 JSON 输出"""
    meeting_id: str = Field(..., description="会议 ID（必须与 analyze 阶段一致以关联产物）")
    summary: SummaryOutput = Field(default_factory=SummaryOutput, description="摘要 Agent 输出")
    actions: ActionOutput = Field(default_factory=ActionOutput, description="待办 Agent 输出")
    insights: InsightOutput = Field(default_factory=InsightOutput, description="洞察 Agent 输出")
    job_config: JobConfig = Field(default_factory=lambda: JobConfig(
        # 渲染接口默认关闭分析 Agent（这是它与 /recording/process 的本质区别）
        enable_summary=False,
        enable_actions=False,
        enable_insights=False,
    ), description="流程控制配置（默认仅开启渲染和分发）")


class RenderResponse(BaseModel):
    """渲染接口响应体"""
    meeting_id: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
    delivery_results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


@router.post("/render", response_model=RenderResponse)
async def render_endpoint(request: RenderRequest):
    """
    渲染接口 — 接受 Agent 输出 JSON，生成 Markdown/PDF/HTML/思维导图报告。

    可选执行外部分发（飞书/Jira/通用Webhook），受 JobConfig 控制。
    产物自动持久化到 workspace/reports/{meeting_id}/checkpoint_render.json。
    """
    meeting_id = request.meeting_id
    job_config = request.job_config
    summary = request.summary
    actions = request.actions
    insights = request.insights
    errors: list[str] = []

    try:
        llm_client = create_llm_client()
        composer = ReportComposer(llm_client=llm_client)
        renderer = ReportRenderer(llm_client=llm_client)
        mindmap_service = MindMapService(llm_client=llm_client)

        md_path = None
        pdf_path = None
        html_path = None
        pdf_generated = False
        mindmap_path = None
        mindmap_generated = False
        final_report_md = ""

        # 1. 报告渲染
        if job_config.enable_report_render:
            final_report_md, kf_objects = await composer.compose_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                keyframes=[],
            )

            title = summary.title if (summary and getattr(summary, "title", None)) else None
            md_path, pdf_path, html_path, pdf_generated = await renderer.render_report(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                kf_objects=kf_objects,
                title=title,
            )
            if not pdf_generated:
                errors.append("PDF 资产生成失败，排版引擎运行异常。")

        # 2. 思维导图
        if job_config.enable_mindmap:
            if not final_report_md:
                final_report_md, _ = await composer.compose_report(
                    meeting_id=meeting_id,
                    summary=summary,
                    actions=actions,
                    insights=insights,
                    keyframes=[],
                )
            title = summary.title if (summary and getattr(summary, "title", None)) else None
            mindmap_path, mindmap_generated = await mindmap_service.generate_and_save_mindmap(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                title=title,
            )

        # 组装资产路径
        artifacts = FollowUpArtifacts(
            markdown_path=str(md_path) if md_path else None,
            pdf_path=str(pdf_path) if pdf_generated else None,
            html_path=str(html_path) if html_path else None,
            mindmap_path=str(mindmap_path) if mindmap_generated else None,
        )

        # 3. 外部分发
        delivery_results: list[DeliveryResult] = []
        if job_config.enable_delivery:
            feishu_client = FeishuClient()
            jira_client = JiraClient()
            delivery_service = ReportDelivery(feishu_client=feishu_client, jira_client=jira_client)

            delivery_results = await delivery_service.deliver_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                pdf_path=pdf_path,
                pdf_generated=pdf_generated,
                mindmap_path=mindmap_path,
                mindmap_generated=mindmap_generated,
                feishu_config=job_config.feishu,
                jira_config=job_config.jira,
            )

            # 通用 Webhook
            if job_config.webhook_urls:
                from datetime import datetime, timezone

                def _dump(obj: Any) -> Any:
                    return obj.model_dump() if hasattr(obj, "model_dump") else obj

                webhook_payload = {
                    "event": "meeting_rendered",
                    "meeting_id": meeting_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "summary": _dump(summary),
                    "actions": _dump(actions),
                    "insights": _dump(insights),
                    "artifacts": _dump(artifacts),
                }
                webhook_service = WebhookService()
                webhook_results = await webhook_service.dispatch(
                    urls=job_config.webhook_urls,
                    payload=webhook_payload,
                )
                delivery_results.extend(webhook_results)

        # 组装响应
        response_data = {
            "meeting_id": meeting_id,
            "artifacts": artifacts.model_dump(),
            "delivery_results": [r.model_dump() for r in delivery_results],
            "errors": errors,
        }

        # 持久化渲染产物
        await _checkpoint.save(meeting_id, "render", response_data)

        return response_data

    except Exception as e:
        logger.exception(f"[RenderEndpoint] 渲染失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
