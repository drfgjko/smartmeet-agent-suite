# -*- coding: utf-8 -*-
"""
Meeting workflow state schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .meeting_schemas import ActionOutput, FollowUpOutput, InsightOutput, SummaryOutput


class MeetingGraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    meeting_id: str = ""
    status: str = "PENDING"
    audio_data: bytes | None = None
    transcript: Any = None
    transcript_text: str = ""
    summary: SummaryOutput = Field(default_factory=SummaryOutput)
    actions: ActionOutput = Field(default_factory=ActionOutput)
    insights: InsightOutput = Field(default_factory=InsightOutput)
    followup: FollowUpOutput = Field(default_factory=FollowUpOutput)
    errors: list[str] = Field(default_factory=list)
