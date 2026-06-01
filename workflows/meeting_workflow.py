# -*- coding: utf-8 -*-
"""
LangGraph 会议处理图 —— 多Agent编排核心
- 编排模式: Pipeline + 并行 (Fan-out / Fan-in)
- 支持 JobConfig 参数级流程控制：按需启停 Agent 节点和 FollowUp 子步骤
"""

from __future__ import annotations
from typing import Any
from langgraph.graph import StateGraph, START, END
from loguru import logger

from agents.summary_agent import SummaryAgent
from agents.action_agent import ActionAgent
from agents.insight_agent import InsightAgent
from agents.followup_agent import FollowUpAgent
from schemas import MeetingGraphState, JobConfig
from services.media_engine import DiarizationResult, ExtractedFrame

_compiled_graph_cache: dict[str, Any] = {}


def _get_cache_key(llm_client, jira_client, feishu_client, job_config: JobConfig) -> str:
    """缓存键：客户端实例 ID + JobConfig 的开关指纹"""
    config_fingerprint = (
        f"{job_config.enable_summary}:{job_config.enable_actions}:{job_config.enable_insights}"
        f":{job_config.any_followup_enabled}"
    )
    return f"{id(llm_client)}:{config_fingerprint}"


def build_meeting_graph(
    llm_client=None,
    jira_client=None,
    feishu_client=None,
    job_config: JobConfig | None = None,
) -> StateGraph:
    """
    根据 JobConfig 动态构建 LangGraph 条件分支图。

    图结构逻辑：
        START ──┬── [summary]  (if enable_summary)  ──┐
                ├── [action]   (if enable_actions)  ──┤── [followup] (if any_followup_enabled) ── END
                └── [insight]  (if enable_insights) ──┘

    若所有分析 Agent 都被关闭，图仅包含一个直通到 END 的空节点。
    """
    if llm_client is None:
        raise ValueError("llm_client is required for meeting graph")

    if job_config is None:
        job_config = JobConfig()

    graph = StateGraph(MeetingGraphState)

    # 收集被启用的分析 Agent 节点名
    enabled_agents: list[str] = []

    if job_config.enable_summary:
        summary_agent = SummaryAgent(llm_client=llm_client)
        graph.add_node("summary", summary_agent.process)
        graph.add_edge(START, "summary")
        enabled_agents.append("summary")

    if job_config.enable_actions:
        action_agent = ActionAgent(llm_client=llm_client, jira_client=jira_client, feishu_client=feishu_client)
        graph.add_node("action", action_agent.process)
        graph.add_edge(START, "action")
        enabled_agents.append("action")

    if job_config.enable_insights:
        insight_agent = InsightAgent(llm_client=llm_client)
        graph.add_node("insight", insight_agent.process)
        graph.add_edge(START, "insight")
        enabled_agents.append("insight")

    # 若所有分析 Agent 都被关闭，添加一个直通空节点
    if not enabled_agents:
        async def _passthrough(state: object) -> dict:
            return {}
        graph.add_node("passthrough", _passthrough)
        graph.add_edge(START, "passthrough")
        graph.add_edge("passthrough", END)
        logger.warning("所有分析 Agent 均被关闭，图仅包含直通节点")
        return graph

    # 判断是否需要 FollowUp 节点
    if job_config.any_followup_enabled:
        followup_agent = FollowUpAgent(
            feishu_client=feishu_client,
            jira_client=jira_client,
            llm_client=llm_client,
        )
        graph.add_node("followup", followup_agent.process)

        for agent_name in enabled_agents:
            graph.add_edge(agent_name, "followup")

        graph.add_edge("followup", END)
    else:
        # FollowUp 全部关闭，分析 Agent 直接到 END
        for agent_name in enabled_agents:
            graph.add_edge(agent_name, END)
        logger.info("FollowUp 子步骤全部关闭，分析 Agent 完成后直接结束")

    logger.info(f"Meeting graph built: agents={enabled_agents}, followup={job_config.any_followup_enabled}")
    return graph


def compile_meeting_graph(
    llm_client: Any = None,
    jira_client: Any = None,
    feishu_client: Any = None,
    job_config: JobConfig | None = None,
) -> Any:
    """编译 LangGraph 图，带缓存（相同客户端+相同开关组合复用编译结果）"""
    if job_config is None:
        job_config = JobConfig()

    cache_key = _get_cache_key(llm_client, jira_client, feishu_client, job_config)
    if cache_key in _compiled_graph_cache:
        return _compiled_graph_cache[cache_key]

    graph = build_meeting_graph(
        llm_client=llm_client,
        jira_client=jira_client,
        feishu_client=feishu_client,
        job_config=job_config,
    )
    compiled = graph.compile()
    _compiled_graph_cache[cache_key] = compiled
    logger.info("Meeting graph compiled and cached successfully")
    return compiled


async def run_meeting_pipeline(
    meeting_id: str,
    transcript_text: str = "",
    transcript: DiarizationResult | None = None,
    keyframes: list[ExtractedFrame] | None = None,
    llm_client: Any = None,
    jira_client: Any = None,
    feishu_client: Any = None,
    job_config: JobConfig | None = None,
) -> dict:
    """
    运行会议分析管线。

    Args:
        meeting_id: 会议唯一标识符
        transcript_text: 带发言人标记的格式化转录文本
        transcript: 说话人声纹分割结果
        keyframes: 视频关键帧列表
        llm_client: 统一 LLM 客户端
        jira_client: Jira 集成客户端
        feishu_client: 飞书集成客户端
        job_config: 任务级流程控制配置，None 时全开
    """
    if job_config is None:
        job_config = JobConfig()

    logger.info(f"Starting meeting pipeline: {meeting_id}")

    initial_state = MeetingGraphState(
        meeting_id=meeting_id,
        transcript_text=transcript_text,
        transcript=transcript,
        keyframes=keyframes or [],
        job_config=job_config,
    )
    compiled_graph = compile_meeting_graph(
        llm_client=llm_client,
        jira_client=jira_client,
        feishu_client=feishu_client,
        job_config=job_config,
    )
    raw_state = await compiled_graph.ainvoke(initial_state)
    final_state = raw_state.model_dump() if hasattr(raw_state, "model_dump") else dict(raw_state)
    errors = final_state.get("errors", [])
    if errors:
        logger.warning(f"Pipeline completed with errors: {errors}")
    else:
        logger.info(f"Pipeline completed successfully for: {meeting_id}")
    return final_state
