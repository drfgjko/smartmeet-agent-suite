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

from services.integrations.llm_client import create_llm_client

def build_meeting_graph(llm_client=None, jira_client=None, feishu_client=None) -> StateGraph:
    from services.integrations.jira_client import JiraClient
    from services.integrations.feishu_client import FeishuClient

    llm = llm_client or create_llm_client()
    jira = jira_client or JiraClient()
    feishu = feishu_client or FeishuClient()
    
    summary_agent = SummaryAgent(llm)
    action_agent = ActionAgent(llm, jira, feishu)
    insight_agent = InsightAgent(llm)
    followup_agent = FollowUpAgent(feishu_client=feishu, jira_client=jira, llm_client=llm)

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

from services.media_engine import DiarizationResult, ExtractedFrame

def compile_meeting_graph(
    llm_client: Any = None,
    jira_client: Any = None,
    feishu_client: Any = None,
) -> Any:
    graph = build_meeting_graph(
        llm_client=llm_client,
        jira_client=jira_client,
        feishu_client=feishu_client,
    )
    compiled = graph.compile()
    logger.info("Meeting graph compiled successfully")
    return compiled

async def run_meeting_pipeline(
    meeting_id: str,
    transcript_text: str = "",
    transcript: DiarizationResult | None = None,
    keyframes: list[ExtractedFrame] | None = None,
    llm_client: Any = None,
    jira_client: Any = None,
    feishu_client: Any = None,
    **kwargs: Any,
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
    final_state = await compiled_graph.ainvoke(initial_state)
    errors = final_state.get("errors", [])
    if errors:
        logger.warning(f"Pipeline completed with errors: {errors}")
    else:
        logger.info(f"Pipeline completed successfully for: {meeting_id}")
    return final_state
