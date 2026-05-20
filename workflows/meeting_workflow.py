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
    llm = llm_client or create_llm_client()
    jira = jira_client
    feishu = feishu_client
    
    summary_agent = SummaryAgent(llm)
    action_agent = ActionAgent(llm, jira, feishu)
    insight_agent = InsightAgent(llm)
    followup_agent = FollowUpAgent(feishu)

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

def compile_meeting_graph(**kwargs) -> Any:
    graph = build_meeting_graph(**kwargs)
    compiled = graph.compile()
    logger.info("Meeting graph compiled successfully")
    return compiled

async def run_meeting_pipeline(meeting_id: str, transcript_text: str = "", transcript: Any = None, **kwargs) -> dict:
    logger.info(f"Starting meeting pipeline: {meeting_id}")
    initial_state = MeetingGraphState(
        meeting_id=meeting_id,
        transcript_text=transcript_text,
        transcript=transcript,
    )
    compiled_graph = compile_meeting_graph(**kwargs)
    final_state = await compiled_graph.ainvoke(initial_state)
    errors = final_state.get("errors", [])
    if errors:
        logger.warning(f"Pipeline completed with errors: {errors}")
    else:
        logger.info(f"Pipeline completed successfully for: {meeting_id}")
    return final_state
