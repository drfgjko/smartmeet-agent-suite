# -*- coding: utf-8 -*-
"""
Summary Agent（摘要Agent）
- 接收转写文本，生成结构化会议纪要
- 使用 LLM 进行内容提取和组织
- 输出: 议题/讨论要点/结论/决策 四层结构
"""

from __future__ import annotations
import asyncio
import json
from loguru import logger

from schemas import SummaryOutput, TopicDetail
from utils.serialization import _state_value

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

# === 新增 Map-Reduce Prompts ===
MAP_SYSTEM_PROMPT = """你是一位专业的会议纪要助手。你的任务是提取一份长会议【局部片段】中的关键信息。
要求：
1. 提取该片段中讨论的核心议题、得出的局部结论、做出的决策和下一步行动。
2. 即使片段很短或信息不全，也请尽量提取。如果没有决策或行动，可以留空列表。
3. 必须严格按照JSON格式输出，不要添加任何其他文字。"""

MAP_USER_PROMPT = """请根据以下会议局部片段生成结构化信息提取。
## 会议局部片段
{chunk}
## 输出格式（严格JSON）
{{
  "topics": [
    {{
      "title": "议题名称",
      "discussion_points": ["要点1", "要点2"],
      "participants": ["发言人1"],
      "conclusion": "该议题的结论"
    }}
  ],
  "decisions": ["决策1"],
  "next_steps": ["下一步1"]
}}"""

REDUCE_SYSTEM_PROMPT = """你是一位高级会议纪要整理专家。你的任务是将多次提取的【局部会议摘要】进行全局合并与去重。
要求：
1. 整合多个局部摘要中的议题，合并相同议题的要点和结论。
2. 汇总并去重所有的决策和下一步行动。
3. 推断整个会议的总体主题(title)、日期(date)和参会人(participants)。
4. 必须严格按照JSON格式输出完整的会议纪要。"""

REDUCE_USER_PROMPT = """请根据以下汇编的局部会议摘要，生成最终的全局会议纪要。
## 局部摘要集合
{combined_summaries}
## 输出格式（严格JSON）
{{
  "title": "全局会议主题",
  "date": "会议日期",
  "participants": ["全局参会人1", "全局参会人2"],
  "topics": [
    {{
      "title": "合并后的议题名称",
      "discussion_points": ["要点1", "要点2"],
      "participants": ["发言人1"],
      "conclusion": "该议题的结论"
    }}
  ],
  "decisions": ["合并去重后的决策1", "决策2"],
  "next_steps": ["合并去重后的下一步1", "下一步2"]
}}"""


class SummaryAgent:
    """
    摘要Agent - 并行阶段的节点之一

    架构说明:
    1. 从 state 读取 transcript_text
    2. 判断文本长度，小于阈值走单次调用，大于阈值走 Map-Reduce 并发调用
    3. 构造 Prompt 调用 LLM
    4. 约束 JSON Schema 输出格式并校验
    5. 写入 state["summary"]

    面试考点:
    - Prompt 设计策略？（System Prompt + Few-shot + JSON Schema约束）
    - 长文本如何处理？（分块摘要 + 合并，MapReduce策略）
    - 并发容错？（局部重试 + 显式日志埋点）
    """
    def __init__(self, *, llm_client=None):
        self.llm = llm_client

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[SummaryAgent] 正在处理会议: {meeting_id}")
        transcript_text = _state_value(state, "transcript_text", "")
        if not transcript_text:
            logger.warning("[SummaryAgent] 缺少可用的转录文本")
            raise ValueError("transcript_text is required for SummaryAgent")
        
        summary = await self._generate_summary(transcript_text)
        logger.info(f"[SummaryAgent] 会议纪要生成完毕: {summary.title}")
        return {"summary": summary}

    def _chunk_text(self, text: str, chunk_size: int = 3000, overlap: int = 200) -> list[str]:
        """将长文本切片，带有指定的交叠长度"""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    async def _map_task(self, chunk: str, index: int, total: int) -> dict:
        """执行单个切片的 Map 任务，包含重试兜底策略"""
        messages = [
            {"role": "system", "content": MAP_SYSTEM_PROMPT},
            {"role": "user", "content": MAP_USER_PROMPT.format(chunk=chunk)}
        ]
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                result = await self.llm.chat_json(messages=messages, temperature=0.3, max_tokens=2048)
                logger.info(f"[SummaryAgent] 切片 {index}/{total} 处理完成")
                return result
            except Exception as e:
                # 显式日志埋点：遵守拒绝静默失败的规范
                if attempt == max_retries:
                    logger.error(f"[SummaryAgent] 切片 {index}/{total} 重试 {max_retries} 次后最终失败: {e}")
                    # 容错兜底：即使某个分片彻底失败，也返回空结构，避免整体崩溃
                    return {"topics": [], "decisions": [], "next_steps": []}
                logger.warning(f"[SummaryAgent] 切片 {index}/{total} 发生异常: {e}，正在进行第 {attempt} 次退避重试...")
                await asyncio.sleep(2 ** attempt)  # 指数退避重试

    async def _reduce_task(self, map_results: list[dict]) -> SummaryOutput:
        """执行所有切片结果的 Reduce 合并任务"""
        logger.info("[SummaryAgent] 开始执行 Reduce 全局合并...")
        # 强制 ensure_ascii=False 遵循编码死命令
        combined_text = json.dumps(map_results, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": REDUCE_SYSTEM_PROMPT},
            {"role": "user", "content": REDUCE_USER_PROMPT.format(combined_summaries=combined_text)}
        ]
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

    async def _generate_summary(self, transcript: str) -> SummaryOutput:
        """核心路由：根据文本长度决定是单次调用还是 Map-Reduce 并发调用"""
        if len(transcript) < 3000:
            # 文本较短，直接单次调用
            logger.info("[SummaryAgent] 文本长度较短，直接执行单次提取")
            messages = [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": SUMMARY_USER_PROMPT.format(transcript=transcript)}
            ]
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
        else:
            # 文本超长，执行 Map-Reduce 策略
            chunks = self._chunk_text(transcript, chunk_size=3000, overlap=200)
            logger.info(f"[SummaryAgent] 文本超长({len(transcript)}字)，切分为 {len(chunks)} 个片段执行 Map-Reduce 并发提取")
            
            # Map阶段：并发执行所有切片任务
            tasks = [self._map_task(chunk, i+1, len(chunks)) for i, chunk in enumerate(chunks)]
            map_results = await asyncio.gather(*tasks)
            
            # Reduce阶段：合并结果
            final_summary = await self._reduce_task(map_results)
            return final_summary
