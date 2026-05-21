# -*- coding: utf-8 -*-
"""
Report Delivery Service
- 负责飞书摘要推送、附件上传及发送
- 负责 Jira 待办附件挂载
- 归并各个渠道分发结果
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from loguru import logger
from typing import Any

from schemas import SummaryOutput, ActionOutput, InsightOutput, DeliveryResult
from services.reporting import (
    format_summary_markdown,
    format_actions_markdown,
    format_insights_markdown,
)


class ReportDelivery:
    def __init__(self, feishu_client: Any = None, jira_client: Any = None):
        self.feishu = feishu_client
        self.jira = jira_client

    async def deliver_report(
        self,
        meeting_id: str,
        summary: SummaryOutput,
        actions: ActionOutput,
        insights: InsightOutput,
        pdf_path: Path | None,
        pdf_generated: bool,
        mindmap_path: Path | None,
        mindmap_generated: bool,
    ) -> list[DeliveryResult]:
        """
        向各个渠道（飞书、Jira 等）分发报告和资产。
        返回 list[DeliveryResult]。
        """
        results = []

        # 1. 飞书分发
        if self.feishu and getattr(self.feishu, "is_enabled", False):
            feishu_result = DeliveryResult(channel="feishu")
            try:
                summary_md = format_summary_markdown(summary)
                actions_md = format_actions_markdown(actions)
                insights_md = format_insights_markdown(insights)
                sent = await self.feishu.send_meeting_summary(
                    title=summary.title or f"会议报告 - {meeting_id}",
                    summary_md=summary_md,
                    action_items_md=actions_md,
                    insights_md=insights_md,
                )
                feishu_result.success = sent
                feishu_result.targets = summary.participants

                # 上传并发送附件消息到飞书群聊
                receive_id = getattr(self.feishu, "receive_id", "")
                if receive_id:
                    logger.info(f"[ReportDelivery] Feishu receive_id configured ({receive_id}). Uploading assets...")
                    if pdf_generated and pdf_path:
                        pdf_key = await self.feishu.upload_file(pdf_path, file_type="pdf")
                        if pdf_key:
                            pdf_sent = await self.feishu.send_file(receive_id=receive_id, file_key=pdf_key)
                            if pdf_sent:
                                feishu_result.artifacts.append(pdf_key)
                            else:
                                logger.error("[ReportDelivery] Feishu PDF send failed")
                                feishu_result.success = False
                        else:
                            logger.error("[ReportDelivery] Feishu PDF upload failed")
                            feishu_result.success = False
                            
                    if mindmap_generated and mindmap_path:
                        mm_key = await self.feishu.upload_file(mindmap_path, file_type="doc")
                        if mm_key:
                            mm_sent = await self.feishu.send_file(receive_id=receive_id, file_key=mm_key)
                            if mm_sent:
                                feishu_result.artifacts.append(mm_key)
                            else:
                                logger.error("[ReportDelivery] Feishu Mindmap send failed")
                                feishu_result.success = False
                        else:
                            logger.error("[ReportDelivery] Feishu Mindmap upload failed")
                            feishu_result.success = False
            except Exception as e:
                logger.error(f"[ReportDelivery] Feishu delivery failed: {e}")
                feishu_result.success = False
                feishu_result.error = str(e)
            results.append(feishu_result)

        # 2. Jira 分发
        jira_issues = [item.jira_issue_key for item in actions.action_items if item.jira_issue_key]
        if self.jira and getattr(self.jira, "is_enabled", False) and jira_issues:
            jira_result = DeliveryResult(channel="jira", targets=jira_issues)
            try:
                logger.info(f"[ReportDelivery] Uploading attachments to Jira issues: {jira_issues}")
                delivery_succeeded = True
                for issue_key in jira_issues:
                    if pdf_generated and pdf_path:
                        pdf_uploaded = await asyncio.to_thread(self.jira.add_attachment, issue_key, pdf_path)
                        if pdf_uploaded:
                            jira_result.artifacts.append(f"{issue_key}:{pdf_path.name}")
                        else:
                            logger.error(f"[ReportDelivery] Failed to upload PDF attachment to Jira issue {issue_key}")
                            delivery_succeeded = False
                            
                    if mindmap_generated and mindmap_path:
                        mm_uploaded = await asyncio.to_thread(self.jira.add_attachment, issue_key, mindmap_path)
                        if mm_uploaded:
                            jira_result.artifacts.append(f"{issue_key}:{mindmap_path.name}")
                        else:
                            logger.error(f"[ReportDelivery] Failed to upload mindmap attachment to Jira issue {issue_key}")
                            delivery_succeeded = False
                            
                jira_result.success = delivery_succeeded
            except Exception as e:
                logger.error(f"[ReportDelivery] Jira delivery failed: {e}")
                jira_result.success = False
                jira_result.error = str(e)
            results.append(jira_result)

        return results
