# -*- coding: utf-8 -*-
"""
Markdown Formatter Utility
- 负责将结构化的会议 Schema 数据（SummaryOutput, ActionOutput, InsightOutput）格式化为标准的 Markdown 文本
- 为无状态纯函数设计，无外部依赖，避免模块循环依赖
"""

from __future__ import annotations

from schemas import SummaryOutput, ActionOutput, InsightOutput


def format_summary_markdown(summary: SummaryOutput) -> str:
    """将会议纪要数据格式化为 Markdown"""
    lines = [f"## {summary.title or '会议纪要'}\n"]
    participants = summary.participants
    if participants:
        lines.append(f"**参会人**: {', '.join(participants)}\n")
    for i, topic in enumerate(summary.topics, 1):
        lines.append(f"### 议题{i}: {topic.title}")
        for point in topic.discussion_points:
            lines.append(f"- {point}")
        if topic.conclusion:
            lines.append(f"- **结论**: {topic.conclusion}")
        lines.append("")
    decisions = summary.decisions
    if decisions:
        lines.append("### 会议决策")
        for d in decisions:
            lines.append(f"- {d}")
        lines.append("")
    next_steps = summary.next_steps
    if next_steps:
        lines.append("### 下一步计划")
        for s in next_steps:
            lines.append(f"- {s}")
    return "\n".join(lines)


def format_actions_markdown(actions: ActionOutput) -> str:
    """将行动项/待办事项数据格式化为 Markdown"""
    if not actions.action_items:
        return "*（无待办事项）*"
    lines = []
    for i, item in enumerate(actions.action_items, 1):
        status_parts = []
        if item.jira_issue_key:
            status_parts.append(f"Jira: {item.jira_issue_key}")
        if item.feishu_task_id:
            status_parts.append(f"飞书: {item.feishu_task_id}")
        status = f" ({', '.join(status_parts)})" if status_parts else ""
        deadline_str = f" | 截止: {item.deadline}" if item.deadline else ""
        lines.append(f"{i}. **{item.assignee or '未指定'}**: {item.task}{deadline_str} [{item.priority}]{status}")
    return "\n".join(lines)


def format_insights_markdown(insights: InsightOutput) -> str:
    """将会议洞察数据格式化为 Markdown"""
    overall = insights.overall_sentiment
    score = insights.sentiment_score
    eff = insights.efficiency_score
    lines = [f"**整体氛围**: {overall} (得分: {score:.2f})", f"**效率评分**: {eff}/10", ""]
    speaker_stats = insights.speaker_stats
    if speaker_stats:
        lines.append("**发言统计**:")
        for s in speaker_stats:
            ratio = s.speaking_ratio
            bar = "█" * int(ratio * 20)
            lines.append(f"- {s.speaker}: {ratio:.1%} {bar} ({s.speaking_duration}s, {s.segment_count}次)")
        lines.append("")
    keywords = insights.keywords
    if keywords:
        lines.append(f"**关键词**: {', '.join(keywords)}")
    highlights = insights.highlights
    if highlights:
        lines.append("\n**亮点**:")
        for h in highlights:
            lines.append(f"- {h}")
    suggestions = insights.suggestions
    if suggestions:
        lines.append("\n**改进建议**:")
        for s in suggestions:
            lines.append(f"- {s}")
    return "\n".join(lines)
