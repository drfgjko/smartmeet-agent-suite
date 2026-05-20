# -*- coding: utf-8 -*-
"""
Follow-up Agent（跟进Agent）
- 汇聚 Summary + Action + Insight 三个Agent的结果
- 通过 Schema 适配层标准化上游输出，降低对上游内部格式的直接依赖
- 生成并发送会议纪要到飞书群
- 确认所有待办已同步
- 设置跟踪提醒
"""

from __future__ import annotations
from datetime import datetime
from loguru import logger

from schemas import SummaryOutput, ActionOutput, InsightOutput, FollowUpOutput


def _state_value(state: object, key: str, default):
    if hasattr(state, key):
        value = getattr(state, key)
        return default if value is None else value
    if isinstance(state, dict):
        return state.get(key, default)
    return default


class FollowUpAgent:
    """
    跟进Agent - Pipeline的最后一个节点（Fan-in汇聚）

    架构说明:
    1. 等待 Summary/Action/Insight 三个并行Agent全部完成
    2. 通过 Schema 适配层标准化上游产物
    3. 汇聚结果，生成完整的会议报告
    4. 推送到飞书群
    5. 检查待办同步状态
    6. 设置定时提醒

    面试考点:
    - Fan-in 汇聚是如何实现的？（LangGraph 多条边汇聚到同一节点）
    - 如果某个并行Agent失败了怎么办？（部分降级，跳过失败部分继续）
    - 提醒机制怎么实现？（APScheduler定时任务 / 消息队列延迟消息）
    """
    def __init__(self, feishu_client=None):
        self.feishu = feishu_client

    @staticmethod
    def _adapt_upstream(state: object) -> tuple[SummaryOutput, ActionOutput, InsightOutput]:
        """标准化适配层：将上游裸 dict 转换为 Schema 对象，隔离上游格式变化。"""
        raw_summary = _state_value(state, "summary", None)
        raw_actions = _state_value(state, "actions", None)
        raw_insights = _state_value(state, "insights", None)

        summary = SummaryOutput.model_validate(raw_summary) if raw_summary is not None else SummaryOutput()
        actions = ActionOutput.model_validate(raw_actions) if raw_actions is not None else ActionOutput()
        insights = InsightOutput.model_validate(raw_insights) if raw_insights is not None else InsightOutput()

        return summary, actions, insights

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[FollowUpAgent] Processing meeting: {meeting_id}")

        # 标准化上游产物
        summary, actions, insights = self._adapt_upstream(state)

        result = FollowUpOutput(meeting_id=meeting_id)
        try:
            summary_md = self._format_summary_markdown(summary)
            actions_md = self._format_actions_markdown(actions)
            insights_md = self._format_insights_markdown(insights)
            if self.feishu and getattr(self.feishu, "is_enabled", False):
                sent = await self.feishu.send_meeting_summary(
                    title=summary.title,
                    summary_md=summary_md,
                    action_items_md=actions_md,
                    insights_md=insights_md,
                )
                result.summary_sent = sent
                result.recipients = summary.participants
            result.jira_issues_created = [item.jira_issue_key for item in actions.action_items if item.jira_issue_key]
            result.feishu_tasks_created = [item.feishu_task_id for item in actions.action_items if item.feishu_task_id]
            result.reminders_scheduled = sum(1 for item in actions.action_items if item.deadline)
            result.report_url = self._generate_report(meeting_id, summary_md, actions_md, insights_md)
            logger.info(f"[FollowUpAgent] Follow-up complete")
            return {"followup": result, "status": "COMPLETED"}
        except Exception as e:
            logger.error(f"[FollowUpAgent] Error: {e}")
            return {
                "errors": _state_value(state, "errors", []) + [f"FollowUpAgent: {str(e)}"],
                "followup": result,
                "status": "COMPLETED",
            }

    @staticmethod
    def _format_summary_markdown(summary: SummaryOutput) -> str:
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

    @staticmethod
    def _format_actions_markdown(actions: ActionOutput) -> str:
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

    @staticmethod
    def _format_insights_markdown(insights: InsightOutput) -> str:
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

    @staticmethod
    def _generate_report(meeting_id: str, summary_md: str, actions_md: str, insights_md: str) -> str:
        report = (
            f"# 会议报告 - {meeting_id}\n\n"
            f"生成时间: {datetime.now().isoformat()}\n\n"
            f"---\n\n"
            f"## 会议纪要\n\n{summary_md}\n\n"
            f"---\n\n"
            f"## 待办事项\n\n{actions_md}\n\n"
            f"---\n\n"
            f"## 会议洞察\n\n{insights_md}\n"
        )
        logger.info(f"Report generated for meeting {meeting_id}")
        return f"/reports/{meeting_id}.md"
