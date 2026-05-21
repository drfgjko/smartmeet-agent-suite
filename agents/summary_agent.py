# -*- coding: utf-8 -*-
"""
Summary Agent（摘要Agent）
- 接收转写文本，生成结构化会议纪要
- 使用 LLM 进行内容提取和组织
- 输出: 议题/讨论要点/结论/决策 四层结构
"""

from __future__ import annotations
from loguru import logger

from schemas import SummaryOutput, TopicDetail
from ._utils import _state_value

SUMMARY_SYSTEM_PROMPT = """你是一位专业的会议纪要助手。你的任务是根据会议转写文本，生成清晰、结构化的会议纪要。
要求：
1. 准确提取会议中的每个议题
2. 每个议题包含讨论要点、参与人、结论
3. 明确列出会议做出的决策
4. 列出下一步行动计划
5. 使用中文输出
你必须严格按照以下JSON格式输出，不要添加任何其他文字："""

SUMMARY_USER_PROMPT = """请根据以下会议转写文本生成结构化会议纪要。
## 会议转写文本
{transcript}
## 输出格式（严格JSON）
{{
  "title": "会议主题（从内容推断）",
  "date": "会议日期（如无法确定则写今天）",
  "participants": ["参会人1", "参会人2"],
  "topics": [
    {{
      "title": "议题名称",
      "discussion_points": ["要点1", "要点2"],
      "participants": ["发言人1"],
      "conclusion": "该议题的结论"
    }}
  ],
  "decisions": ["决策1", "决策2"],
  "next_steps": ["下一步1", "下一步2"]
}}"""

class SummaryAgent:
    """
    摘要Agent - 并行阶段的节点之一

    架构说明:
    1. 从 state 读取 transcript_text
    2. 构造 Few-shot Prompt 调用 LLM
    3. 约束 JSON Schema 输出格式
    4. 解析并验证结果
    5. 写入 state["summary"]

    面试考点:
    - Prompt 设计策略？（System Prompt + Few-shot + JSON Schema约束）
    - 如何保证输出格式正确？（response_format + 解析降级）
    - 长文本如何处理？（分块摘要 + 合并，MapReduce策略）
    """
    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[SummaryAgent] Processing meeting: {meeting_id}")
        transcript_text = _state_value(state, "transcript_text", "")
        if not transcript_text:
            logger.warning("[SummaryAgent] No transcript text available")
            return {"summary": SummaryOutput(title="未知会议")}
        try:
            summary = await self._generate_summary(transcript_text)
            logger.info(f"[SummaryAgent] Summary generated: {summary.title}")
            return {"summary": summary}
        except Exception as e:
            logger.error(f"[SummaryAgent] Error: {e}")
            return {
                "errors": _state_value(state, "errors", []) + [f"SummaryAgent: {str(e)}"],
                "summary": self._generate_fallback_summary(transcript_text),
            }

    async def _generate_summary(self, transcript: str) -> SummaryOutput:
        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": SUMMARY_USER_PROMPT.format(transcript=transcript)}
        ]
        if self.llm is None:
            return self._generate_fallback_summary(transcript)
        result = await self.llm.chat_json(messages=messages, temperature=0.3, max_tokens=4096)
        topics = [
            TopicDetail.model_validate(topic)
            for topic in result.get("topics", [])
            if isinstance(topic, dict)
        ]
        return SummaryOutput(
            title=result.get("title", "会议纪要"),
            date=result.get("date", ""),
            participants=result.get("participants", []),
            topics=topics,
            decisions=result.get("decisions", []),
            next_steps=result.get("next_steps", []),
        )

    @staticmethod
    def _generate_fallback_summary(transcript: str) -> SummaryOutput:
        lines = transcript.strip().split("\n")
        speakers = set()
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                speaker_part = parts[0].strip()
                if "]" in speaker_part:
                    speaker_part = speaker_part.split("]", 1)[-1].strip()
                speakers.add(speaker_part)
        participants = sorted(speakers)
        return SummaryOutput(
            title="会议纪要（自动摘要降级模式）",
            date="",
            participants=participants,
            topics=[
                TopicDetail(
                    title="会议内容",
                    discussion_points=["（LLM调用失败，请查看原始转写文本）"],
                    participants=participants,
                    conclusion="",
                )
            ],
            decisions=[],
            next_steps=[],
        )
