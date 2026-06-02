# -*- coding: utf-8 -*-
"""
JobConfig — 任务级流程控制配置契约

所有入口（CLI、API /recording/process、/analyze、/render）共用同一套 JobConfig 机制。
不调用新参数时的默认行为（全开）是字段默认值的自然结果，不存在额外的兼容代码。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobConfig(BaseModel):
    """
    任务级流程控制配置。

    设计原则：
    - 所有布尔开关默认 True，保证不传 JobConfig 时行为与改造前完全一致
    - webhook_urls 默认空列表，不传则不触发通用 Webhook
    - 此模型贯穿 API 层 → application_service → meeting_workflow → Agent 全链路
    """

    # ── Agent 节点开关 ──
    enable_speaker_inference: bool = True  # 是否运行发言人推断 Agent
    enable_summary: bool = True       # 是否运行摘要 Agent
    enable_actions: bool = True       # 是否运行待办 Agent
    enable_insights: bool = True      # 是否运行洞察 Agent

    # ── FollowUp 子步骤开关 ──
    enable_report_render: bool = True  # 是否渲染 Markdown/PDF/HTML 报告
    enable_mindmap: bool = True        # 是否生成思维导图
    enable_delivery: bool = True       # 是否执行外部分发（飞书/Jira/Webhook）

    # ── 外部分发通道开关 ──
    enable_feishu: bool = True         # 是否推送飞书（受限于 .env 中是否配置凭证）
    enable_jira: bool = True           # 是否同步 Jira

    # ── 通用 Webhook ──
    webhook_urls: list[str] = Field(
        default_factory=list,
        description="通用 Webhook 目标地址列表，系统将标准化 JSON payload POST 到这些 URL",
    )

    @property
    def any_agent_enabled(self) -> bool:
        """是否有至少一个分析 Agent 被启用"""
        return self.enable_summary or self.enable_actions or self.enable_insights

    @property
    def any_followup_enabled(self) -> bool:
        """是否有至少一个 FollowUp 子步骤被启用"""
        return self.enable_report_render or self.enable_mindmap or self.enable_delivery
