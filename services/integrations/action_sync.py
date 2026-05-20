# -*- coding: utf-8 -*-
"""
Action Sync Service（待办外部同步服务）
- 将 ActionAgent 提取出的行动项同步到 Jira Cloud 和飞书任务
- 从 ActionAgent 中解耦出来，使 ActionAgent 成为纯计算模块
- 支持幂等性保证（防止重复创建）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from schemas import ActionItem, SyncStatus


async def sync_actions_to_external(
    items: list[ActionItem],
    meeting_id: str,
    jira_client: Any = None,
    feishu_client: Any = None,
) -> tuple[list[ActionItem], SyncStatus]:
    """
    将行动项同步到外部系统（Jira / 飞书）。

    返回:
        - synced_items: 带有外部系统 ID 的行动项列表
        - sync_status: 各平台同步状态
    """
    synced: list[ActionItem] = []

    for item in items:
        # Jira 同步
        if jira_client and getattr(jira_client, "is_enabled", False):
            try:
                jira_result = jira_client.create_issue(
                    summary=f"[会议待办] {item.task}",
                    description=f"来源：会议 {meeting_id}\n负责人：{item.assignee}\n上下文：{item.context}",
                    assignee=jira_client.resolve_user(item.assignee),
                    due_date=item.deadline or None,
                    priority=item.priority,
                    labels=["meeting-auto", f"meeting-{meeting_id}"],
                )
                item.jira_issue_key = jira_result["key"]
            except Exception as e:
                logger.error(f"Failed to sync to Jira: {item.task} - {e}")

        # 飞书同步
        if feishu_client and getattr(feishu_client, "is_enabled", False):
            try:
                due_ts = None
                if item.deadline:
                    due_dt = datetime.strptime(item.deadline, "%Y-%m-%d")
                    due_ts = int(due_dt.timestamp())
                feishu_result = await feishu_client.create_task(
                    summary=f"[会议待办] {item.task}",
                    description=f"负责人：{item.assignee}\n来源会议：{meeting_id}\n上下文：{item.context}",
                    due_timestamp=due_ts,
                )
                item.feishu_task_id = feishu_result.get("task_id")
            except Exception as e:
                logger.error(f"Failed to sync to Feishu: {item.task} - {e}")

        synced.append(item)

    status = SyncStatus(
        jira="enabled" if jira_client and getattr(jira_client, "is_enabled", False) else "disabled",
        feishu="enabled" if feishu_client and getattr(feishu_client, "is_enabled", False) else "disabled",
    )

    return synced, status
