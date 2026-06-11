# -*- coding: utf-8 -*-
"""
会议工作流状态 Schema
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from engines.media import DiarizationResult, ExtractedFrame
from .job_config import JobConfig
from .meeting_schemas import ActionOutput, FollowUpOutput, InsightOutput, SummaryOutput


class MeetingGraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    meeting_id: str = ""                             # 会议唯一标识符
    status: str = "PENDING"                          # 工作流处理状态 (如 PENDING, COMPLETED 等)
    job_config: JobConfig = Field(default_factory=JobConfig)  # 任务级流程控制配置
    audio_data: bytes | None = None                  # 原始音频二进制数据
    transcript: DiarizationResult | None = None      # 说话人声纹分割与转录结果结构体
    transcript_text: str = ""                        # 带有发言人标记的格式化转录文本
    summary: SummaryOutput = Field(default_factory=SummaryOutput)        # 会议纪要生成产物
    actions: ActionOutput = Field(default_factory=ActionOutput)          # 待办事项与外部系统同步状态
    insights: InsightOutput = Field(default_factory=InsightOutput)        # 情绪和效率评估洞察
    followup: FollowUpOutput = Field(default_factory=FollowUpOutput)      # 资产生成、推送分发的归档结果
    keyframes: list[ExtractedFrame] = Field(default_factory=list)         # 视频关键帧列表（图像路径及对齐字幕）
    errors: list[str] = Field(default_factory=list)                      # 链路中产生的错误信息列表

