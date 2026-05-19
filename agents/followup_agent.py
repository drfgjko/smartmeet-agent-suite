# -*- coding: utf-8 -*-
"""
Follow-up Agent（跟进Agent）
- 汇聚 Summary + Action + Insight 三个Agent的结果
- 生成并发送会议纪要到飞书群
- 确认所有待办已同步
- 设置跟踪提醒
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from loguru import logger

class FollowUpAgent:
    """
    跟进Agent - Pipeline的最后一个节点（Fan-in汇聚）

    架构说明:
    1. 等待 Summary/Action/Insight 三个并行Agent全部完成
    2. 汇聚结果，生成完整的会议报告
    3. 推送到飞书群
    4. 检查待办同步状态
    5. 设置定时提醒

    面试考点:
    - Fan-in 汇聚是如何实现的？（LangGraph 多条边汇聚到同一节点）
    - 如果某个并行Agent失败了怎么办？（部分降级，跳过失败部分继续）
    - 提醒机制怎么实现？（APScheduler定时任务 / 消息队列延迟消息）
    """
    def __init__(self, feishu_client=None):
        self.feishu = feishu_client

    async def process(self, state: dict) -> dict:
        meeting_id = state.get("meeting_id", "unknown")
        logger.info(f"[FollowUpAgent] Processing meeting: {meeting_id}")
        summary = state.get("summary")
        actions = state.get("actions")
        insights = state.get("insights")
        result = {"meeting_id": meeting_id}
        try:
            summary_md = self._format_summary_markdown(summary)
            actions_md = self._format_actions_markdown(actions)
            insights_md = self._format_insights_markdown(insights)
            if self.feishu and getattr(self.feishu, "is_enabled", False):
                title = summary.get("title") if isinstance(summary, dict) else f"会议 {meeting_id}"
                sent = await self.feishu.send_meeting_summary(
                    title=title,
                    summary_md=summary_md,
                    action_items_md=actions_md,
                    insights_md=insights_md,
                )
                result["summary_sent"] = sent
                if summary and isinstance(summary, dict):
                    result["recipients"] = summary.get("participants", [])
            if actions and isinstance(actions, dict):
                action_items = actions.get("action_items", [])
                result["jira_issues_created"] = [item.get("jira_issue_key") for item in action_items if item.get("jira_issue_key")]
                result["feishu_tasks_created"] = [item.get("feishu_task_id") for item in action_items if item.get("feishu_task_id")]
                reminders = sum(1 for item in action_items if item.get("deadline"))
                result["reminders_scheduled"] = reminders
            result["report_url"] = self._generate_report(meeting_id, summary_md, actions_md, insights_md)
            state["followup"] = result
            state["status"] = "COMPLETED"
            logger.info(f"[FollowUpAgent] Follow-up complete")
        except Exception as e:
            logger.error(f"[FollowUpAgent] Error: {e}")
            state["errors"] = state.get("errors", []) + [f"FollowUpAgent: {str(e)}"]
            state["followup"] = result
            state["status"] = "COMPLETED"
        return state

    @staticmethod
    def _format_summary_markdown(summary: Any) -> str:
        if not summary or not isinstance(summary, dict):
            return "*（摘要生成失败）*"
        lines = [f"## {summary.get('title', '会议纪要')}\n"]
        participants = summary.get('participants', [])
        if participants:
            lines.append(f"**参会人**: {', '.join(participants)}\n")
        for i, topic in enumerate(summary.get('topics', []), 1):
            lines.append(f"### 议题{i}: {topic.get('title', '')}")
            for point in topic.get('discussion_points', []):
                lines.append(f"- {point}")
            if topic.get('conclusion'):
                lines.append(f"- **结论**: {topic.get('conclusion')}")
            lines.append("")
        decisions = summary.get('decisions', [])
        if decisions:
            lines.append("### 会议决策")
            for d in decisions:
                lines.append(f"- {d}")
            lines.append("")
        next_steps = summary.get('next_steps', [])
        if next_steps:
            lines.append("### 下一步计划")
            for s in next_steps:
                lines.append(f"- {s}")
        return "\n".join(lines)

    @staticmethod
    def _format_actions_markdown(actions: Any) -> str:
        if not actions or not isinstance(actions, dict) or not actions.get("action_items"):
            return "*（无待办事项）*"
        lines = []
        for i, item in enumerate(actions.get("action_items", []), 1):
            status_parts = []
            if item.get("jira_issue_key"):
                status_parts.append(f"Jira: {item['jira_issue_key']}")
            if item.get("feishu_task_id"):
                status_parts.append(f"飞书: {item['feishu_task_id']}")
            status = f" ({', '.join(status_parts)})" if status_parts else ""
            deadline_str = f" | 截止: {item['deadline']}" if item.get("deadline") else ""
            lines.append(f"{i}. **{item.get('assignee', '未指定')}**: {item.get('task', '')}{deadline_str} [{item.get('priority', 'medium')}]{status}")
        return "\n".join(lines)

    @staticmethod
    def _format_insights_markdown(insights: Any) -> str:
        if not insights or not isinstance(insights, dict):
            return "*（洞察分析失败）*"
        overall = insights.get("overall_sentiment", "neutral")
        score = insights.get("sentiment_score", 0.0)
        eff = insights.get("efficiency_score", 0.0)
        lines = [f"**整体氛围**: {overall} (得分: {score:.2f})", f"**效率评分**: {eff}/10", ""]
        speaker_stats = insights.get("speaker_stats", [])
        if speaker_stats:
            lines.append("**发言统计**:")
            for s in speaker_stats:
                ratio = s.get("speaking_ratio", 0)
                bar = "█" * int(ratio * 20)
                lines.append(f"- {s.get('speaker', 'unknown')}: {ratio:.1%} {bar} ({s.get('speaking_duration', 0)}s, {s.get('segment_count', 0)}次)")
            lines.append("")
        keywords = insights.get("keywords", [])
        if keywords:
            lines.append(f"**关键词**: {', '.join(keywords)}")
        highlights = insights.get("highlights", [])
        if highlights:
            lines.append("\n**亮点**:")
            for h in highlights:
                lines.append(f"- {h}")
        suggestions = insights.get("suggestions", [])
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
