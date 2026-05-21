# -*- coding: utf-8 -*-
"""
Follow-up Agent（跟进Agent）
- 汇聚 Summary + Action + Insight 三个Agent的结果
- 通过 Schema 适配层标准化上游输出，降低对上游内部格式的直接依赖
- 调用报表组装服务生成 Markdown 报告，做关键帧 LLM 智能融合排版
- 调用报告渲染服务生成多轨 PDF/HTML 会议资产
- 调用脑图服务生成思维导图
- 调用分发服务将生成的资产推送并挂载至飞书与 Jira，实现闭环
"""

from __future__ import annotations

from typing import Any
from loguru import logger

from schemas import (
    SummaryOutput,
    ActionOutput,
    InsightOutput,
    FollowUpOutput,
    FollowUpArtifacts,
)
from services import ReportComposer, ReportRenderer, MindMapService, ReportDelivery
from ._utils import _state_value


class FollowUpAgent:
    """
    跟进Agent - Pipeline的最后一个节点（Fan-in汇聚）

    架构说明:
    1. 等待 Summary/Action/Insight 三个并行Agent全部完成
    2. 通过 Schema 适配层标准化上游产物
    3. 调用报表组装服务生成 Markdown 报告，做关键帧 LLM 智能融合排版
    4. 调用报告渲染服务生成多轨 PDF/HTML 会议资产
    5. 调用脑图服务生成思维导图
    6. 调用分发服务将生成的资产推送并挂载至飞书与 Jira，实现闭环
    """
    def __init__(self, feishu_client=None, jira_client=None, llm_client=None):
        self.feishu = feishu_client
        self.jira = jira_client
        self.llm = llm_client
        self._composer = ReportComposer(llm_client=self.llm)
        self._renderer = ReportRenderer()
        self._mindmap_service = MindMapService(llm_client=self.llm)
        self._delivery = ReportDelivery(feishu_client=self.feishu, jira_client=self.jira)

    @staticmethod
    def _adapt_upstream(state: object) -> tuple[SummaryOutput, ActionOutput, InsightOutput]:
        """标准化适配层：将上游裸 dict 转换为 Schema 对象，隔离上游格式变化。"""
        raw_summary = _state_value(state, "summary", None)
        raw_actions = _state_value(state, "actions", None)
        raw_insights = _state_value(state, "insights", None)

        summary = SummaryOutput.model_validate(raw_summary) if raw_summary is not None else SummaryOutput()
        actions = ActionOutput.model_validate(raw_actions) if raw_actions is not None else ActionOutput()
        insights = InsightOutput.model_validate(raw_insights) if raw_insights is not None else InsightOutput()

        return summary, actions, insights

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[FollowUpAgent] Processing meeting: {meeting_id}")

        # 标准化上游产物
        summary, actions, insights = self._adapt_upstream(state)

        result = FollowUpOutput(meeting_id=meeting_id)
        errors: list[str] = _state_value(state, "errors", [])
        step_failures: list[str] = []

        # 1. 报告内容生成（核心步骤，失败则终止）
        try:
            final_report_md, kf_objects = await self._composer.compose_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                keyframes=_state_value(state, "keyframes", [])
            )
        except Exception as e:
            logger.exception(f"[FollowUpAgent] compose_report failed: {e}")
            errors.append(f"FollowUpAgent.compose_report: {str(e)}")
            return {"followup": result, "errors": errors, "status": "ERROR"}

        # 2. 报告编译与渲染（非核心，失败则跳过）
        md_path = pdf_path = html_path = None
        pdf_generated = False
        try:
            md_path, pdf_path, html_path, pdf_generated = await self._renderer.render_report(
                meeting_id=meeting_id,
                final_report_md=final_report_md,
                kf_objects=kf_objects
            )
        except Exception as e:
            logger.warning(f"[FollowUpAgent] render_report failed, skipping: {e}")
            errors.append(f"FollowUpAgent.render_report: {str(e)}")
            step_failures.append("render")

        # 3. 思维导图生成（非核心，失败则跳过）
        mindmap_path = None
        mindmap_generated = False
        try:
            mindmap_path, mindmap_generated = await self._mindmap_service.generate_and_save_mindmap(
                meeting_id=meeting_id,
                final_report_md=final_report_md
            )
        except Exception as e:
            logger.warning(f"[FollowUpAgent] generate_mindmap failed, skipping: {e}")
            errors.append(f"FollowUpAgent.generate_mindmap: {str(e)}")
            step_failures.append("mindmap")

        # 保存资产路径至结构化字段中
        result.artifacts = FollowUpArtifacts(
            markdown_path=str(md_path) if md_path else None,
            pdf_path=str(pdf_path) if pdf_path else None,
            html_path=str(html_path) if html_path else None,
            mindmap_path=str(mindmap_path) if mindmap_generated else None
        )

        # 4. 外部分发与渠道挂载（非核心，失败则跳过）
        try:
            delivery_results = await self._delivery.deliver_report(
                meeting_id=meeting_id,
                summary=summary,
                actions=actions,
                insights=insights,
                pdf_path=pdf_path,
                pdf_generated=pdf_generated,
                mindmap_path=mindmap_path,
                mindmap_generated=mindmap_generated,
            )
            result.delivery_results = delivery_results
        except Exception as e:
            logger.warning(f"[FollowUpAgent] deliver_report failed, skipping: {e}")
            errors.append(f"FollowUpAgent.deliver_report: {str(e)}")
            step_failures.append("delivery")

        status = "COMPLETED" if not step_failures else "PARTIAL"
        logger.info(f"[FollowUpAgent] Follow-up {status}, failed steps: {step_failures or 'none'}")
        return {"followup": result, "errors": errors, "status": status}

