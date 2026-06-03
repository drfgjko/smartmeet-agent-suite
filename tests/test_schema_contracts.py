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
            "artifacts": {
                "markdown_path": "/reports/mtg-001.md",
                "pdf_path": "/reports/mtg-001.pdf",
            },
            "delivery_results": [
                {
                    "channel": "feishu",
                    "success": True,
                    "targets": ["Alice", "Bob"],
                    "artifacts": ["key_123"],
                }
            ],
        }
        output = FollowUpOutput.model_validate(data)
        assert output.artifacts.markdown_path == "/reports/mtg-001.md"
        assert output.artifacts.pdf_path == "/reports/mtg-001.pdf"
        assert output.artifacts.html_path is None
        assert len(output.delivery_results) == 1
        assert output.delivery_results[0].channel == "feishu"
        assert output.delivery_results[0].success is True


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

    def test_accepts_media_engine_types(self):
        from services.media_engine import DiarizationResult, DiarizedSegment, ExtractedFrame
        from pathlib import Path

        transcript = DiarizationResult(
            segments=[DiarizedSegment(start=0.0, end=1.0, text="hello", speaker="Speaker 1")],
            num_speakers=1,
            speakers=["Speaker 1"],
            language="zh",
        )
        keyframes = [ExtractedFrame(path=Path("dummy.jpg"), timestamp=1.5)]

        state = MeetingGraphState(
            transcript=transcript,
            keyframes=keyframes,
        )
        assert state.transcript is not None
        assert state.transcript.num_speakers == 1
        assert len(state.keyframes) == 1
        assert state.keyframes[0].timestamp == 1.5
