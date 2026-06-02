# -*- coding: utf-8 -*-
"""
Follow-up Agent（跟进Agent）
- 汇聚 Summary + Action + Insight 三个Agent的结果
- 通过 Schema 适配层标准化上游输出，降低对上游内部格式的直接依赖
- 根据 JobConfig 控制子步骤：报告渲染、思维导图生成、外部分发
- 调用报表组装服务生成 Markdown 报告，做关键帧 LLM 智能融合排版
- 调用报告渲染服务生成多轨 PDF/HTML 会议资产
- 调用脑图服务生成思维导图
- 调用分发服务将生成的资产推送并挂载至飞书与 Jira，实现闭环
- 调用通用 Webhook 服务推送标准化 JSON 到用户配置的外部 URL
"""

from __future__ import annotations

from typing import Any
from loguru import logger

from schemas import (
    JobConfig,
    SummaryOutput,
    ActionOutput,
    InsightOutput,
    FollowUpOutput,
    FollowUpArtifacts,
    MeetingGraphState,
)
from services import ReportComposer, ReportRenderer, MindMapService, ReportDelivery
from services.delivery import WebhookService
from ._utils import _state_value


class FollowUpAgent:
    """
    跟进Agent - Pipeline的最后一个节点（Fan-in汇聚）

    架构说明:
    1. 等待 Summary/Action/Insight 三个并行Agent全部完成
    2. 通过 Schema 适配层标准化上游产物
    3. 根据 state.job_config 中的开关决定执行哪些子步骤
    4. 调用报表组装服务生成 Markdown 报告，做关键帧 LLM 智能融合排版
    5. 调用报告渲染服务生成多轨 PDF/HTML 会议资产
    6. 调用脑图服务生成思维导图
    7. 调用分发服务将生成的资产推送并挂载至飞书与 Jira，实现闭环
    8. 调用通用 Webhook 服务推送到用户配置的外部 URL
    """
    def __init__(self, *, feishu_client=None, jira_client=None, llm_client=None):
        self.feishu = feishu_client
        self.jira = jira_client
        self.llm = llm_client
        self._composer = ReportComposer(llm_client=self.llm)
        self._renderer = ReportRenderer()
        self._mindmap_service = MindMapService(llm_client=self.llm)
        self._delivery = ReportDelivery(feishu_client=self.feishu, jira_client=self.jira)
        self._webhook = WebhookService()

    @staticmethod
    def _adapt_upstream(state: MeetingGraphState) -> tuple[SummaryOutput, ActionOutput, InsightOutput]:
        return state.summary, state.actions, state.insights

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[FollowUpAgent] 正在处理会议: {meeting_id}")

        # 读取 JobConfig（不存在时使用全开默认值）
        job_config: JobConfig = _state_value(state, "job_config", JobConfig())

        # 标准化上游产物
        summary, actions, insights = self._adapt_upstream(state)

        result = FollowUpOutput(meeting_id=meeting_id)
        errors: list[str] = _state_value(state, "errors", [])

        md_path = None
        pdf_path = None
        html_path = None
        pdf_generated = False
        mindmap_path = None
        mindmap_generated = False
        final_report_md = ""

        # 1. 报告内容生成与渲染（受 enable_report_render 控制）
        if job_config.enable_report_render:
            final_report_md, kf_objects = await self._composer.compose_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                keyframes=_state_value(state, "keyframes", [])
            )

            # 提取 LLM 生成的会议标题
            title = summary.title if (summary and getattr(summary, "title", None)) else None

            md_path, pdf_path, html_path, pdf_generated = await self._renderer.render_report(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                kf_objects=kf_objects,
                title=title
            )
            if not pdf_generated:
                errors.append("PDF 资产生成失败，排版引擎运行异常。")
        else:
            logger.info("[FollowUpAgent] 报告渲染已跳过 (enable_report_render=False)")

        # 2. 思维导图生成（受 enable_mindmap 控制）
        if job_config.enable_mindmap:
            # 如果报告渲染被跳过但思维导图需要生成，先组装报告内容
            if not final_report_md:
                final_report_md, _ = await self._composer.compose_report(
                    meeting_id=meeting_id,
                    summary=summary,
                    actions=actions,
                    insights=insights,
                    keyframes=_state_value(state, "keyframes", [])
                )

            title = summary.title if (summary and getattr(summary, "title", None)) else None
            mindmap_path, mindmap_generated = await self._mindmap_service.generate_and_save_mindmap(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                title=title
            )
        else:
            logger.info("[FollowUpAgent] 思维导图生成已跳过 (enable_mindmap=False)")

        # 保存资产路径至结构化字段中
        result.artifacts = FollowUpArtifacts(
            markdown_path=str(md_path) if md_path else None,
            pdf_path=str(pdf_path) if pdf_generated else None,
            html_path=str(html_path) if html_path else None,
            mindmap_path=str(mindmap_path) if mindmap_generated else None
        )

        # 3. 外部分发与渠道挂载（受 enable_delivery 控制）
        if job_config.enable_delivery:
            # 3a. 飞书/Jira 专用通道分发（受 enable_feishu / enable_jira 进一步控制）
            delivery_results = await self._delivery.deliver_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                pdf_path=pdf_path,
                pdf_generated=pdf_generated,
                mindmap_path=mindmap_path,
                mindmap_generated=mindmap_generated,
                enable_feishu=job_config.enable_feishu,
                enable_jira=job_config.enable_jira,
            )
            result.delivery_results = delivery_results

            # 3b. 通用 Webhook 推送
            if job_config.webhook_urls:
                webhook_payload = self._build_webhook_payload(
                    meeting_id=meeting_id,
                    summary=summary,
                    actions=actions,
                    insights=insights,
                    artifacts=result.artifacts,
                )
                webhook_results = await self._webhook.dispatch(
                    urls=job_config.webhook_urls,
                    payload=webhook_payload,
                )
                result.delivery_results.extend(webhook_results)
        else:
            logger.info("[FollowUpAgent] 外部分发已跳过 (enable_delivery=False)")

        logger.info(f"[FollowUpAgent] 后续处理完成")
        return {"followup": result, "errors": errors, "status": "COMPLETED"}

    @staticmethod
    def _build_webhook_payload(
        meeting_id: str,
        summary: SummaryOutput,
        actions: ActionOutput,
        insights: InsightOutput,
        artifacts: FollowUpArtifacts,
    ) -> dict:
        """组装标准化 Webhook payload"""
        from datetime import datetime, timezone

        def _dump(obj: Any) -> Any:
            return obj.model_dump() if hasattr(obj, "model_dump") else obj

        return {
            "event": "meeting_completed",
            "meeting_id": meeting_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": _dump(summary),
            "actions": _dump(actions),
            "insights": _dump(insights),
            "artifacts": _dump(artifacts),
        }

    async def close(self):
        pass
