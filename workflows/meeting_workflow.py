# -*- coding: utf-8 -*-
"""
LangGraph 会议处理图 —— 多Agent编排核心
- 编排模式: Pipeline + 并行 (Fan-out / Fan-in)
"""

from __future__ import annotations
from typing import Any
from langgraph.graph import StateGraph, START, END
from loguru import logger

from agents.summary_agent import SummaryAgent
from agents.action_agent import ActionAgent
from agents.insight_agent import InsightAgent
from agents.followup_agent import FollowUpAgent
from schemas import MeetingGraphState
from services.media_engine import DiarizationResult, ExtractedFrame

_compiled_graph_cache: dict[str, Any] = {}


def _get_cache_key(llm_client, jira_client, feishu_client) -> str:
    return str(id(llm_client))


def build_meeting_graph(llm_client=None, jira_client=None, feishu_client=None) -> StateGraph:

    if llm_client is None:
        raise ValueError("llm_client is required for meeting graph")
    
    summary_agent = SummaryAgent(llm_client=llm_client)
    action_agent = ActionAgent(llm_client=llm_client, jira_client=jira_client, feishu_client=feishu_client)
    insight_agent = InsightAgent(llm_client=llm_client)
    followup_agent = FollowUpAgent(feishu_client=feishu_client, jira_client=jira_client, llm_client=llm_client)

    graph = StateGraph(MeetingGraphState)

    graph.add_node("summary", summary_agent.process)
    graph.add_node("action", action_agent.process)
    graph.add_node("insight", insight_agent.process)
    graph.add_node("followup", followup_agent.process)

    graph.add_edge(START, "summary")
    graph.add_edge(START, "action")
    graph.add_edge(START, "insight")

    graph.add_edge("summary", "followup")
    graph.add_edge("action", "followup")
    graph.add_edge("insight", "followup")

    graph.add_edge("followup", END)

    logger.info("Meeting graph built successfully")
    return graph

def compile_meeting_graph(
    llm_client: Any = None,
    jira_client: Any = None,
    feishu_client: Any = None,
) -> Any:
    cache_key = _get_cache_key(llm_client, jira_client, feishu_client)
    if cache_key in _compiled_graph_cache:
        return _compiled_graph_cache[cache_key]

    graph = build_meeting_graph(
        llm_client=llm_client,
        jira_client=jira_client,
        feishu_client=feishu_client,
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
) -> dict:
    logger.info(f"Starting meeting pipeline: {meeting_id}")
    
    initial_state = MeetingGraphState(
        meeting_id=meeting_id,
        transcript_text=transcript_text,
        transcript=transcript,
        keyframes=keyframes or [],
    )
    compiled_graph = compile_meeting_graph(
        llm_client=llm_client,
        jira_client=jira_client,
        feishu_client=feishu_client,
    )
    raw_state = await compiled_graph.ainvoke(initial_state)
    final_state = raw_state.model_dump() if hasattr(raw_state, "model_dump") else dict(raw_state)
    errors = final_state.get("errors", [])
    if errors:
        logger.warning(f"Pipeline completed with errors: {errors}")
    else:
        logger.info(f"Pipeline completed successfully for: {meeting_id}")
    return final_state
