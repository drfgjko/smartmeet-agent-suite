# -*- coding: utf-8 -*-
"""
Report Composer Service
- 负责组装基础报告草稿 (Markdown 文本)
- 提取并标准化关键帧，结合大模型做图文智能融合排版
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from loguru import logger

from schemas import SummaryOutput, ActionOutput, InsightOutput
from services.media_engine import ExtractedFrame
from .markdown_formatter import (
    format_summary_markdown,
    format_actions_markdown,
    format_insights_markdown,
)


LAYOUT_SYSTEM_PROMPT = """你是一位专业的文档排版专家。
你的任务是将提供的会议报告（包含会议纪要、待办事项和会议洞察）与视频中提取的关键帧进行智能融合。
你需要根据关键帧的时间戳、字幕文本，将 {IMAGE:N} 标记（其中 N 为 1 到 关键帧数量 之间的整数）优雅地插入到报告正文中相关的段落后面。
同时，在每个 {IMAGE:N} 占位符下方添加一行简短的斜体配图说明（例如：*图 N：视频时间戳 XX:XX 处，发言人正在展示 XX 方案*）。

排版规则：
1. 不要大幅修改报告的原始文字，只做排版插入和配图说明。
2. 保持原有的标题层级（## 和 ###）与列表格式。
3. 如果某些关键帧与正文内容关联性较弱，也可以在报告中单独分节或追加，但要保持图文呼应的逻辑。
4. 输出必须是合法的 Markdown 文本。
"""

LAYOUT_USER_PROMPT = """请对以下会议报告和视频关键帧进行智能图文融合排版。

## 视频关键帧列表：
{keyframes_desc}

## 会议报告草稿：
{draft_report}
"""


class ReportComposer:
    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    async def compose_report(
        self,
        meeting_id: str,
        summary: SummaryOutput,
        actions: ActionOutput,
        insights: InsightOutput,
        keyframes: list[Any],
    ) -> tuple[str, list[ExtractedFrame]]:
        """
        进行上游报告格式化、关键帧标准化，以及大模型智能融合排版，返回排版后的Markdown正文和标准化关键帧列表。
        """
        # 1. 格式化基础纪要、行动项和洞察
        summary_md = format_summary_markdown(summary)
        actions_md = format_actions_markdown(actions)
        insights_md = format_insights_markdown(insights)

        # 2. 合并草稿
        draft_report = (
            f"# 会议报告 - {meeting_id}\n\n"
            f"生成时间: {datetime.now().isoformat()}\n\n"
            f"---\n\n"
            f"## 会议纪要\n\n{summary_md}\n\n"
            f"---\n\n"
            f"## 待办事项\n\n{actions_md}\n\n"
            f"---\n\n"
            f"## 会议洞察\n\n{insights_md}\n"
        )

        final_report_md = draft_report

        # 3. 关键帧标准化
        kf_objects = []
        if keyframes:
            for f in keyframes:
                if isinstance(f, ExtractedFrame):
                    kf_objects.append(f)
                elif isinstance(f, dict):
                    p = Path(f["path"]) if "path" in f else Path("")
                    kf_objects.append(ExtractedFrame(
                        path=p,
                        timestamp=f.get("timestamp", 0.0),
                        subtitle_text=f.get("subtitle_text", ""),
                        caption=f.get("caption", ""),
                    ))

        # 4. LLM 智能融合排版
        if kf_objects and self.llm:
            logger.info(f"[ReportComposer] Aligning {len(kf_objects)} keyframes with LLM...")
            kf_desc_items = []
            for idx, kf in enumerate(kf_objects, 1):
                ts = kf.timestamp_str
                sub = kf.subtitle_text or "无画面字幕/视频帧"
                kf_desc_items.append(f"Fig.{idx} at {ts}: {sub}")
            keyframes_desc = "\n".join(kf_desc_items)

            messages = [
                {"role": "system", "content": LAYOUT_SYSTEM_PROMPT},
                {"role": "user", "content": LAYOUT_USER_PROMPT.format(keyframes_desc=keyframes_desc, draft_report=draft_report)}
            ]
            try:
                final_report_md = await self.llm.chat(messages=messages, temperature=0.3, max_tokens=4096)
                logger.info("[ReportComposer] Dynamic keyframe alignment completed successfully")
            except Exception as e:
                logger.error(f"[ReportComposer] Keyframe alignment LLM pass failed: {e}. Falling back to raw draft.")
                final_report_md = draft_report

        return final_report_md, kf_objects
