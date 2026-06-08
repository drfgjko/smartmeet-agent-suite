# -*- coding: utf-8 -*-
"""
Report Composer Service
- 负责组装基础报告草稿 (Markdown 文本)
- 提取并标准化关键帧，结合大模型做图文智能融合排版
"""

from __future__ import annotations

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


LAYOUT_SYSTEM_PROMPT = """你是一位顶级的知识创作者和学术讲义编辑。
你的任务是将一系列干瘪枯燥的会议数据点（议题、待办、洞察），彻底打碎并溶解，重新创作出一篇【行云流水、逻辑连贯、适合出版的深度知识长文（Lecture Note）】。

排版与重组的绝对法则：
1. **彻底摒弃四股文结构**：绝不能出现“## 会议纪要”、“## 待办事项”、“## 会议洞察”这种刻板且割裂的标题！你要把“待办事项”巧妙地作为“下一步演进与计划”的段落融入长文中，将“发言时间/洞察”作为背景介绍融入开头或结尾。让全篇浑然一体。
2. **长篇沉浸式扩写**：绝不能仅仅是罗列骨架。要根据你对知识的深刻理解，把干瘪的议题发散成大段的专业知识分析、案例拆解和原理讲解。
3. **图文智能穿插**：如果提供了视频关键帧 {IMAGE:N}，你必须在相关知识段落中**原封不动地**输出 `{IMAGE:N}` 这个占位符（包含大括号和内部字母数字，绝对不能把它改写成“如图1”、“图N”等自然语言）。系统后续会通过正则识别并替换它。请在占位符的下一行，用斜体写一句对该画面的简短描述。
4. **高端排版组件**：抛弃无聊的加粗，你要在知识讲授的关键点，大量使用以下高亮框增强期刊感：
   {IMPORTANT}这里提炼核心思想、方法论或最终定论{/IMPORTANT}
   {KNOWLEDGE}这里补充行业背景、前置概念或术语科普{/KNOWLEDGE}
   {WARNING}这里指出常见的误区、技术瓶颈或落地风险{/WARNING}
   （注意：必须成对使用闭合标签，绝不可省略 {/IMPORTANT} 等后缀！）
5. 输出必须是合法的纯 Markdown 文本，并给文章起一个响亮的主标题（#开头）。
"""

LAYOUT_USER_PROMPT = """请对以下素材进行彻底解构与重生：

## 视频画面线索（如果有）：
{keyframes_desc}

## 提供的事实依据素材（干瘪数据，请将其彻底溶解到长文中，绝不要照搬里面的死板标题）：
{reference_data}
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
        # 调用方（offline_processor）保证传入 Pydantic 对象，此处直接使用
        summary_md = format_summary_markdown(summary)
        actions_md = format_actions_markdown(actions)
        insights_md = format_insights_markdown(insights)

        # 2. 组装参考素材（不再作为最终报告）
        reference_data = (
            f"=== 议题与讨论 ===\n{summary_md}\n\n"
            f"=== 行动计划与决策 ===\n{actions_md}\n\n"
            f"=== 沟通与行为洞察 ===\n{insights_md}\n"
        )

        final_report_md = f"# 会议报告 - {meeting_id}\n\n请配置 LLM 客户端以启用连贯长文讲义生成功能。\n\n" + reference_data

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

        # 4. LLM 智能重塑为连续讲义（只要有 LLM 就必须触发）
        if self.llm:
            logger.info("[ReportComposer] 正在使用大模型将结构化数据重组为连贯的长文讲义...")
            kf_desc_items = []
            if kf_objects:
                for idx, kf in enumerate(kf_objects, 1):
                    ts = kf.timestamp_str
                    sub = kf.subtitle_text or "无画面字幕/视频帧"
                    kf_desc_items.append(f"{{IMAGE:{idx}}} at {ts}: {sub}")
            keyframes_desc = "\n".join(kf_desc_items) if kf_desc_items else "（本录音无视频关键帧，纯音频生成）"

            messages = [
                {"role": "system", "content": LAYOUT_SYSTEM_PROMPT},
                {"role": "user", "content": LAYOUT_USER_PROMPT.format(keyframes_desc=keyframes_desc, reference_data=reference_data)}
            ]
            final_report_md = await self.llm.chat(messages=messages, temperature=0.4, max_tokens=6000)
            
            # 剥除可能的大模型代码块包裹
            final_report_md = final_report_md.strip()
            if final_report_md.startswith("```markdown"):
                final_report_md = final_report_md[11:].strip()
            elif final_report_md.startswith("```"):
                final_report_md = final_report_md[3:].strip()
            if final_report_md.endswith("```"):
                final_report_md = final_report_md[:-3].strip()
                
            logger.info("[ReportComposer] 连贯的长文讲义生成成功。")

        return final_report_md, kf_objects
