# -*- coding: utf-8 -*-
"""
SmartMeet Schema Contracts（数据契约层）
- 定义 Agent 间传递的结构化数据模型
- 用 Pydantic BaseModel 替代裸 dict，使模块边界从"约定"变为"接口"
- 所有 Agent 的 process() 输出必须符合此处定义的模型
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ─── SpeakerInferenceAgent 内部契约 ──────────────────────────────

class SpeakerMapItem(BaseModel):
    original_label: str = Field(description="原始发言人标签，如 'Speaker 1'")
    inferred_name: str = Field(description="推断出的真实姓名，如 '张三'。如果无法推断，则与原标签相同。")


class SpeakerMapping(BaseModel):
    mappings: list[SpeakerMapItem] = Field(default_factory=list, description="发言人映射关系列表")


# ─── SummaryAgent 输出契约 ───────────────────────────────────────

class TopicDetail(BaseModel):
    title: str = ""
    discussion_points: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    conclusion: str = ""


class SummaryOutput(BaseModel):
    title: str = "会议纪要"
    date: str = ""
    participants: list[str] = Field(default_factory=list)
    topics: list[TopicDetail] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


# ─── ActionAgent 输出契约 ────────────────────────────────────────

class ActionItem(BaseModel):
    assignee: str = "未指定"
    task: str = ""
    deadline: str = ""
    priority: str = "medium"
    context: str = ""
    jira_issue_key: str | None = None
    feishu_task_id: str | None = None


class SyncStatus(BaseModel):
    jira: str = "disabled"
    feishu: str = "disabled"


class ActionOutput(BaseModel):
    meeting_id: str = ""
    action_items: list[ActionItem] = Field(default_factory=list)
    sync_status: SyncStatus = Field(default_factory=SyncStatus)


# ─── InsightAgent 输出契约 ───────────────────────────────────────

class SpeakerStat(BaseModel):
    speaker: str = "unknown"
    speaking_duration: float = 0.0
    speaking_ratio: float = 0.0
    word_count: int = 0
    segment_count: int = 0


class InsightOutput(BaseModel):
    meeting_id: str = ""
    overall_sentiment: str = "neutral"
    sentiment_score: float = 0.5
    speaker_stats: list[SpeakerStat] = Field(default_factory=list)
    efficiency_score: float = 5.0
    keywords: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ─── FollowUpAgent 输出契约 ──────────────────────────────────────

class ReportAsset(BaseModel):
    asset_type: str = ""
    path: str = ""
    generated: bool = False


class DeliveryResult(BaseModel):
    channel: str = ""
    success: bool = False
    partial_success: bool = False
    targets: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    asset_errors: list[str] = Field(default_factory=list)
    error: str | None = None


class FollowUpArtifacts(BaseModel):
    markdown_path: str | None = None
    pdf_path: str | None = None
    html_path: str | None = None
    mindmap_path: str | None = None


class FollowUpOutput(BaseModel):
    meeting_id: str = ""
    artifacts: FollowUpArtifacts = Field(default_factory=FollowUpArtifacts)
    delivery_results: list[DeliveryResult] = Field(default_factory=list)

