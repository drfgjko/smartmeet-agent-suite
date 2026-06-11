# -*- coding: utf-8 -*-
"""
纯交付接口 — POST /api/v1/deliver

接受已有分析 JSON 产物，跳过分析与图渲染阶段，纯做交付（建任务/发报告卡片等）。
主要为了在失败时能够通过 CLI 或者后续流程人工触发重新进行网络同步和交付。
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
from services import ReportDelivery
from services.delivery import WebhookService
from infrastructure.external import FeishuClient, JiraClient, sync_actions_to_external

router = APIRouter(prefix="/api/v1", tags=["deliver"])


class DeliverRequest(BaseModel):
    meeting_id: str
    summary: SummaryOutput = Field(default_factory=SummaryOutput)
    actions: ActionOutput = Field(default_factory=ActionOutput)
    insights: InsightOutput = Field(default_factory=InsightOutput)
    output_files: dict[str, str] = Field(default_factory=dict, description="已生成的资源路径 (如 pdf, mindmap 等)")
    job_config: JobConfig = Field(default_factory=lambda: JobConfig(
        # deliver 端点默认关闭分析和渲染
        enable_summary=False, enable_actions=False, enable_insights=False,
        enable_report_render=False, enable_mindmap=False,
        # 报告分发默认开启，任务同步默认关闭
        enable_delivery=True, enable_task_sync=False,
    ))


class DeliverResponse(BaseModel):
    meeting_id: str
    synced_actions: ActionOutput | None = None
    delivery_results: list[DeliveryResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


@router.post("/deliver", response_model=DeliverResponse)
async def deliver_endpoint(request: DeliverRequest):
    meeting_id = request.meeting_id
    job_config = request.job_config
    summary = request.summary
    actions = request.actions
    insights = request.insights
    output_files = request.output_files
    errors: list[str] = []

    try:
        feishu_client = FeishuClient()
        jira_client = JiraClient()
        
        synced_actions = None
        delivery_results: list[DeliveryResult] = []

        # 1. 任务同步（受 enable_task_sync 控制）
        if job_config.enable_task_sync:
            logger.info(f"[DeliverEndpoint] 开始任务同步: {meeting_id}")
            try:
                synced_items, sync_status = await sync_actions_to_external(
                    items=actions.action_items,
                    meeting_id=meeting_id,
                    jira_client=jira_client,
                    feishu_client=feishu_client,
                    jira_config=job_config.jira,
                    feishu_config=job_config.feishu,
                )
                synced_actions = ActionOutput(
                    meeting_id=meeting_id,
                    action_items=synced_items,
                    sync_status=sync_status,
                )
            except Exception as e:
                logger.error(f"[DeliverEndpoint] 任务同步失败: {e}")
                errors.append(f"任务同步失败: {str(e)}")

        # 2. 报告分发（受 enable_delivery 控制）
        if job_config.enable_delivery:
            logger.info(f"[DeliverEndpoint] 开始报告分发: {meeting_id}")
            delivery_service = ReportDelivery(feishu_client=feishu_client, jira_client=jira_client)
            
            pdf_path_str = output_files.get("pdf")
            mindmap_path_str = output_files.get("mindmap")
            
            from pathlib import Path
            pdf_path = Path(pdf_path_str) if pdf_path_str else None
            mindmap_path = Path(mindmap_path_str) if mindmap_path_str else None

            try:
                d_results = await delivery_service.deliver_report(
                    meeting_id=meeting_id,
                    summary=summary,
                    actions=synced_actions or actions, # 如果同步过，优先使用带 id 的 actions
                    insights=insights,
                    pdf_path=pdf_path,
                    pdf_generated=bool(pdf_path),
                    mindmap_path=mindmap_path,
                    mindmap_generated=bool(mindmap_path),
                    feishu_config=job_config.feishu,
                    jira_config=job_config.jira,
                )
                delivery_results.extend(d_results)
            except Exception as e:
                logger.error(f"[DeliverEndpoint] 报告分发失败: {e}")
                errors.append(f"报告分发失败: {str(e)}")

        # 3. 通用 Webhook（如有配置）
        if job_config.webhook_urls:
            logger.info(f"[DeliverEndpoint] 开始触发 Webhook: {meeting_id}")
            try:
                from datetime import datetime, timezone

                def _dump(obj: Any) -> Any:
                    return obj.model_dump() if hasattr(obj, "model_dump") else obj
                
                artifacts = FollowUpArtifacts(
                    markdown_path=output_files.get("markdown"),
                    pdf_path=output_files.get("pdf"),
                    html_path=output_files.get("html"),
                    mindmap_path=output_files.get("mindmap"),
                )

                webhook_payload = {
                    "event": "meeting_delivered",
                    "meeting_id": meeting_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "summary": _dump(summary),
                    "actions": _dump(synced_actions or actions),
                    "insights": _dump(insights),
                    "artifacts": _dump(artifacts),
                }
                webhook_service = WebhookService()
                webhook_results = await webhook_service.dispatch(
                    urls=job_config.webhook_urls,
                    payload=webhook_payload,
                )
                delivery_results.extend(webhook_results)
            except Exception as e:
                logger.error(f"[DeliverEndpoint] Webhook 分发失败: {e}")
                errors.append(f"Webhook 分发失败: {str(e)}")

        return DeliverResponse(
            meeting_id=meeting_id,
            synced_actions=synced_actions,
            delivery_results=delivery_results,
            errors=errors,
        )

    except Exception as e:
        logger.exception(f"[DeliverEndpoint] 交付端点严重错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
