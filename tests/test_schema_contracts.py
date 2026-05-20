# -*- coding: utf-8 -*-
"""
Schema Contract Tests（契约测试）
- 验证每个 Agent 的输出能被对应 Schema 正确解析
- 验证 FollowUpAgent 的适配层能正确标准化上游输出
- 不依赖 LLM 或外部服务，纯结构验证
"""


from schemas import (
    SummaryOutput,
    ActionOutput,
    ActionItem,
    InsightOutput,
    FollowUpOutput,
    MeetingGraphState,
)


class TestSummaryOutputContract:
    """SummaryAgent 输出契约验证"""

    def test_full_output_parses(self):
        data = {
            "title": "周会",
            "date": "2026-05-20",
            "participants": ["Alice", "Bob"],
            "topics": [
                {
                    "title": "需求讨论",
                    "discussion_points": ["点1", "点2"],
                    "participants": ["Alice"],
                    "conclusion": "通过",
                }
            ],
            "decisions": ["决策1"],
            "next_steps": ["下一步1"],
        }
        output = SummaryOutput.model_validate(data)
        assert output.title == "周会"
        assert len(output.topics) == 1
        assert output.topics[0].title == "需求讨论"

    def test_empty_output_has_defaults(self):
        output = SummaryOutput()
        assert output.title == "会议纪要"
        assert output.participants == []
        assert output.topics == []

    def test_partial_output_fills_defaults(self):
        data = {"title": "临时会议"}
        output = SummaryOutput.model_validate(data)
        assert output.title == "临时会议"
        assert output.decisions == []


class TestActionOutputContract:
    """ActionAgent 输出契约验证"""

    def test_full_output_parses(self):
        data = {
            "meeting_id": "mtg-001",
            "action_items": [
                {
                    "assignee": "Alice",
                    "task": "完成设计文档",
                    "deadline": "2026-05-25",
                    "priority": "high",
                    "context": "需求评审后",
                    "jira_issue_key": "PROJ-123",
                    "feishu_task_id": "task-456",
                }
            ],
            "sync_status": {"jira": "enabled", "feishu": "enabled"},
        }
        output = ActionOutput.model_validate(data)
        assert output.meeting_id == "mtg-001"
        assert len(output.action_items) == 1
        assert output.action_items[0].assignee == "Alice"
        assert output.sync_status.jira == "enabled"

    def test_empty_output_has_defaults(self):
        output = ActionOutput()
        assert output.action_items == []
        assert output.sync_status.jira == "disabled"

    def test_action_item_without_external_ids(self):
        item = ActionItem(assignee="Bob", task="Review PR")
        assert item.jira_issue_key is None
        assert item.feishu_task_id is None


class TestInsightOutputContract:
    """InsightAgent 输出契约验证"""

    def test_full_output_parses(self):
        data = {
            "meeting_id": "mtg-001",
            "overall_sentiment": "positive",
            "sentiment_score": 0.85,
            "speaker_stats": [
                {
                    "speaker": "Alice",
                    "speaking_duration": 120.5,
                    "speaking_ratio": 0.6,
                    "word_count": 500,
                    "segment_count": 10,
                }
            ],
            "efficiency_score": 8.5,
            "keywords": ["架构", "测试"],
            "highlights": ["亮点1"],
            "suggestions": ["建议1"],
        }
        output = InsightOutput.model_validate(data)
        assert output.overall_sentiment == "positive"
        assert len(output.speaker_stats) == 1
        assert output.speaker_stats[0].speaker == "Alice"

    def test_empty_output_has_defaults(self):
        output = InsightOutput()
        assert output.overall_sentiment == "neutral"
        assert output.sentiment_score == 0.5
        assert output.efficiency_score == 5.0


class TestFollowUpOutputContract:
    """FollowUpAgent 输出契约验证"""

    def test_full_output_parses(self):
        data = {
            "meeting_id": "mtg-001",
            "summary_sent": True,
            "recipients": ["Alice", "Bob"],
            "jira_issues_created": ["PROJ-123"],
            "feishu_tasks_created": ["task-456"],
            "reminders_scheduled": 2,
            "report_url": "/reports/mtg-001.md",
        }
        output = FollowUpOutput.model_validate(data)
        assert output.summary_sent is True
        assert output.reminders_scheduled == 2

    def test_empty_output_has_defaults(self):
        output = FollowUpOutput()
        assert output.summary_sent is False
        assert output.report_url == ""


class TestFollowUpAdaptUpstream:
    """FollowUpAgent._adapt_upstream 标准化适配层验证"""

    def test_adapts_valid_upstream(self):
        from agents.followup_agent import FollowUpAgent

        state = {
            "summary": {"title": "周会", "participants": ["Alice"]},
            "actions": {"meeting_id": "mtg-001", "action_items": []},
            "insights": {"meeting_id": "mtg-001", "overall_sentiment": "positive"},
        }
        summary, actions, insights = FollowUpAgent._adapt_upstream(state)
        assert isinstance(summary, SummaryOutput)
        assert summary.title == "周会"
        assert isinstance(actions, ActionOutput)
        assert isinstance(insights, InsightOutput)
        assert insights.overall_sentiment == "positive"

    def test_adapts_missing_upstream_gracefully(self):
        from agents.followup_agent import FollowUpAgent

        state = {}
        summary, actions, insights = FollowUpAgent._adapt_upstream(state)
        assert summary.title == "会议纪要"
        assert actions.action_items == []
        assert insights.overall_sentiment == "neutral"

    def test_adapts_none_upstream_gracefully(self):
        from agents.followup_agent import FollowUpAgent

        state = {"summary": None, "actions": None, "insights": None}
        summary, actions, insights = FollowUpAgent._adapt_upstream(state)
        assert isinstance(summary, SummaryOutput)
        assert isinstance(actions, ActionOutput)
        assert isinstance(insights, InsightOutput)

    def test_adapts_typed_state(self):
        from agents.followup_agent import FollowUpAgent

        state = MeetingGraphState(
            summary=SummaryOutput(title="例会"),
            actions=ActionOutput(meeting_id="mtg-002"),
            insights=InsightOutput(meeting_id="mtg-002", overall_sentiment="neutral"),
        )
        summary, actions, insights = FollowUpAgent._adapt_upstream(state)
        assert summary.title == "例会"
        assert actions.meeting_id == "mtg-002"
        assert insights.overall_sentiment == "neutral"


class TestCrossAgentContractCompatibility:
    """跨 Agent 契约兼容性测试：验证一个 Agent 的输出能被下游正确消费"""

    def test_summary_agent_output_consumed_by_followup(self):
        from agents.followup_agent import FollowUpAgent

        summary_data = {
            "title": "产品评审会",
            "date": "2026-05-20",
            "participants": ["PM", "Dev", "QA"],
            "topics": [{"title": "需求1", "discussion_points": ["点1"], "participants": ["PM"], "conclusion": "通过"}],
            "decisions": ["上线"],
            "next_steps": ["编写文档"],
        }
        summary, _, _ = FollowUpAgent._adapt_upstream({"summary": summary_data})
        assert summary.title == "产品评审会"
        assert len(summary.participants) == 3

    def test_action_agent_output_consumed_by_followup(self):
        from agents.followup_agent import FollowUpAgent

        action_data = {
            "meeting_id": "mtg-001",
            "action_items": [
                {"assignee": "Dev", "task": "修 bug", "deadline": "2026-05-25", "priority": "high", "context": "紧急"}
            ],
            "sync_status": {"jira": "enabled", "feishu": "disabled"},
        }
        _, actions, _ = FollowUpAgent._adapt_upstream({"actions": action_data})
        assert len(actions.action_items) == 1
        assert actions.sync_status.jira == "enabled"

    def test_insight_agent_output_consumed_by_followup(self):
        from agents.followup_agent import FollowUpAgent

        insight_data = {
            "meeting_id": "mtg-001",
            "overall_sentiment": "neutral",
            "sentiment_score": 0.6,
            "speaker_stats": [
                {
                    "speaker": "QA",
                    "speaking_duration": 45.0,
                    "speaking_ratio": 0.3,
                    "word_count": 120,
                    "segment_count": 4,
                }
            ],
            "efficiency_score": 7.5,
            "keywords": ["测试", "发布"],
            "highlights": ["风险已识别"],
            "suggestions": ["缩短无效讨论"],
        }
        _, _, insights = FollowUpAgent._adapt_upstream({"insights": insight_data})
        assert insights.meeting_id == "mtg-001"
        assert insights.speaker_stats[0].speaker == "QA"


class TestMeetingGraphStateContract:
    def test_defaults_are_typed_objects(self):
        state = MeetingGraphState()
        assert isinstance(state.summary, SummaryOutput)
        assert isinstance(state.actions, ActionOutput)
        assert isinstance(state.insights, InsightOutput)
        assert isinstance(state.followup, FollowUpOutput)
        assert state.errors == []
        assert state.status == "PENDING"

    def test_accepts_agent_outputs_as_schema_objects(self):
        state = MeetingGraphState(
            meeting_id="mtg-003",
            summary=SummaryOutput(title="周会"),
            actions=ActionOutput(meeting_id="mtg-003"),
            insights=InsightOutput(meeting_id="mtg-003"),
            followup=FollowUpOutput(meeting_id="mtg-003"),
        )
        assert state.summary.title == "周会"
        assert state.actions.meeting_id == "mtg-003"

    def test_validates_nested_dicts_into_schema_objects(self):
        state = MeetingGraphState(
            summary={"title": "项目会"},
            actions={"meeting_id": "mtg-004"},
            insights={"meeting_id": "mtg-004"},
            followup={"meeting_id": "mtg-004"},
        )
        assert isinstance(state.summary, SummaryOutput)
        assert isinstance(state.actions, ActionOutput)
        assert isinstance(state.insights, InsightOutput)
        assert isinstance(state.followup, FollowUpOutput)
