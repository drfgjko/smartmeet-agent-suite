# -*- coding: utf-8 -*-
"""
Action Agent（待办Agent）
- 从转写文本中提取行动项（谁/做什么/截止时间）
- 只负责认知推理并返回 JSON，不再直接触发任何网络同步
"""

from __future__ import annotations

from datetime import datetime
from loguru import logger

from schemas import ActionItem, ActionOutput
from utils.serialization import _state_value

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
    待办Agent - 纯计算分析节点

    架构说明:
    1. 从 state 读取 transcript_text
    2. LLM 提取行动项三元组（谁/做什么/截止时间）
    3. 返回 ActionOutput

    注意: 此模块不执行外部系统（飞书/Jira）的网络同步操作。
    """
    def __init__(self, *, llm_client=None):
        self.llm = llm_client

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[ActionAgent] 正在处理会议: {meeting_id}")
        transcript_text = _state_value(state, "transcript_text", "")
        if not transcript_text:
            logger.warning("[ActionAgent] 缺少可用的转录文本")
            raise ValueError("transcript_text is required for ActionAgent")
        
        action_items = await self._extract_actions(transcript_text)

        output = ActionOutput(
            meeting_id=meeting_id,
            action_items=action_items,
        )
        logger.info(f"[ActionAgent] 共提取了 {len(action_items)} 个待办事项")
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
