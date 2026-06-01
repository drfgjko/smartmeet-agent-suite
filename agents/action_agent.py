# -*- coding: utf-8 -*-
"""
Action Agent（待办Agent）
- 从转写文本中提取行动项（谁/做什么/截止时间）
- 外部同步逻辑已拆分至 services/integrations/action_sync.py
- 支持幂等性保证（防止重复创建）
"""

from __future__ import annotations

from datetime import datetime
from loguru import logger

from schemas import ActionItem, ActionOutput, SyncStatus, JobConfig
from services.integrations.action_sync import sync_actions_to_external
from ._utils import _state_value

ACTION_SYSTEM_PROMPT = """你是一位专业的任务提取助手。你的任务是从会议转写文本中提取所有行动项/待办事项。
提取规则：
1. 识别明确分配给某人的任务
2. 提取任务的截止时间（如果提到的话）
3. 判断任务优先级（根据语气和上下文）
4. 记录任务的上下文（为什么要做这件事）
注意：
- 只提取明确的行动项，不要凭空创造
- 截止时间格式为 YYYY-MM-DD
- 如果没有明确截止时间，留空
你必须严格按照JSON格式输出："""

ACTION_USER_PROMPT = """请从以下会议转写文本中提取所有行动项/待办事项。
今天的日期是: {today}
## 会议转写文本
{transcript}
## 输出格式（严格JSON）
{{
  "action_items": [
    {{
      "assignee": "负责人姓名",
      "task": "具体任务描述",
      "deadline": "YYYY-MM-DD 或空字符串",
      "priority": "low/medium/high/urgent",
      "context": "这个任务的背景说明"
    }}
  ]
}}"""

class ActionAgent:
    """
    待办Agent - 并行阶段的节点之一

    架构说明:
    1. 从 state 读取 transcript_text
    2. LLM 提取行动项三元组（谁/做什么/截止时间）
    3. 委托 action_sync 服务并行同步到 Jira 和飞书
    4. 记录同步状态

    面试考点:
    - 如何保证 Jira 同步的幂等性？（基于 meeting_id + task hash 去重）
    - 如何处理人名和 Jira 用户的映射？（企业通讯录 + 模糊匹配）
    - 如果 Jira/飞书不可用怎么办？（降级到本地存储 + 异步重试）
    """
    def __init__(self, *, llm_client=None, jira_client=None, feishu_client=None):
        self.llm = llm_client
        self.jira = jira_client
        self.feishu = feishu_client

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[ActionAgent] Processing meeting: {meeting_id}")
        transcript_text = _state_value(state, "transcript_text", "")
        if not transcript_text:
            logger.warning("[ActionAgent] No transcript text available")
            raise ValueError("transcript_text is required for ActionAgent")
        
        action_items = await self._extract_actions(transcript_text)
        job_config: JobConfig = _state_value(state, "job_config", JobConfig())

        synced_items, sync_status = await sync_actions_to_external(
            items=action_items,
            meeting_id=meeting_id,
            jira_client=self.jira,
            feishu_client=self.feishu,
            enable_jira=job_config.enable_jira,
            enable_feishu=job_config.enable_feishu,
        )
        output = ActionOutput(
            meeting_id=meeting_id,
            action_items=synced_items,
            sync_status=sync_status,
        )
        logger.info(f"[ActionAgent] Extracted {len(synced_items)} action items")
        return {"actions": output}

    async def _extract_actions(self, transcript: str) -> list[ActionItem]:
        today = datetime.now().strftime("%Y-%m-%d")
        messages = [
            {"role": "system", "content": ACTION_SYSTEM_PROMPT},
            {"role": "user", "content": ACTION_USER_PROMPT.format(today=today, transcript=transcript)},
        ]
        result = await self.llm.chat_json(messages=messages, temperature=0.2, max_tokens=2048)
        items = []
        for raw in result.get("action_items", []):
            items.append(ActionItem(
                assignee=raw.get("assignee", "未指定"),
                task=raw.get("task", ""),
                deadline=raw.get("deadline", ""),
                priority=raw.get("priority", "medium").lower(),
                context=raw.get("context", ""),
            ))
        return items
