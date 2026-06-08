# -*- coding: utf-8 -*-
"""Jira Cloud 集成客户端 - 自动创建和管理待办事项"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

class JiraClient:
    """
    Jira Cloud REST API 客户端

    职责:
    - 创建 Issue（从会议待办自动同步）
    - 查询 Issue 状态（用于跟踪待办完成情况）
    - 更新 Issue（添加评论等）

    API 文档: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
    """
    def __init__(self, server=None, email=None, api_token=None, project_key="MEET", user_mapping=None):
        self.server = server or os.getenv("JIRA_SERVER", "")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN", "")
        self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY", "MEET")
        self._jira = None
        self._enabled = bool(self.server and self.email and self.api_token)
        raw_mapping = user_mapping or os.getenv("JIRA_USER_MAPPING", "{}")
        if isinstance(raw_mapping, str):
            try:
                import json
                self.USER_MAPPING: dict[str, str] = json.loads(raw_mapping)
            except json.JSONDecodeError:
                logger.warning(f"无效的 JIRA_USER_MAPPING JSON，将使用空映射字典")
                self.USER_MAPPING: dict[str, str] = {}
        else:
            self.USER_MAPPING: dict[str, str] = raw_mapping or {}

    def _get_client(self):
        if self._jira is None and self._enabled:
            from jira import JIRA
            self._jira = JIRA(server=self.server, basic_auth=(self.email, self.api_token))
        return self._jira

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def create_issue(self, summary: str, description: str = "", assignee: str | None = None, due_date: str | None = None, priority: str = "Medium", issue_type: str = "Task", labels: list[str] | None = None) -> dict[str, str]:
        if not self._enabled:
            logger.warning("未配置 Jira 集成参数，跳过创建任务")
            return {"key": "DISABLED", "id": "", "url": ""}
        client = self._get_client()
        fields: dict[str, Any] = {
            "project": {"key": self.project_key},
            "summary": summary,
            "description": description or f"自动创建自会议助手系统\n\n{summary}",
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
        if assignee:
            fields["assignee"] = {"name": assignee}
        if due_date:
            fields["duedate"] = due_date
        if labels:
            fields["labels"] = labels + ["meeting-auto"]
        else:
            fields["labels"] = ["meeting-auto"]
        issue = client.create_issue(fields=fields)
        result = {"key": issue.key, "id": str(issue.id), "url": f"{self.server}/browse/{issue.key}"}
        logger.info(f"成功创建 Jira 任务: {result['key']} - {summary}")
        return result

    def get_issue_status(self, issue_key: str) -> str:
        if not self._enabled:
            return "DISABLED"
        client = self._get_client()
        issue = client.issue(issue_key)
        return str(issue.fields.status)

    def add_comment(self, issue_key: str, comment: str) -> None:
        if not self._enabled:
            return
        client = self._get_client()
        client.add_comment(issue_key, comment)
        logger.info(f"成功向任务添加评论: {issue_key}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def add_attachment(self, issue_key: str, file_path: str | Path, filename: str | None = None) -> bool:
        """
        上传文件作为 Jira Issue 的附件
        """
        if not self._enabled:
            logger.warning("未配置 Jira 集成参数，跳过添加附件")
            return False
        client = self._get_client()
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"找不到需要上传的附件文件: {file_path}")
                return False
            client.add_attachment(issue=issue_key, attachment=str(path.resolve()), filename=filename or path.name)
            logger.info(f"成功将附件 {path.name} 上传至 Jira 任务 {issue_key}")
            return True
        except Exception as e:
            logger.error(f"无法将附件上传至 Jira 任务 {issue_key}: {e}")
            return False

    def resolve_user(self, display_name: str) -> str | None:
        return self.USER_MAPPING.get(display_name)

    @staticmethod
    def map_priority(priority: str) -> str:
        mapping = {"low": "Low", "medium": "Medium", "high": "High", "urgent": "Highest"}
        return mapping.get(priority.lower(), "Medium")
