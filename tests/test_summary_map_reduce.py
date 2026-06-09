# -*- coding: utf-8 -*-
"""
Test for SummaryAgent MapReduce logic
"""
import pytest
import asyncio
from unittest.mock import AsyncMock

from agents.summary_agent import SummaryAgent

@pytest.mark.asyncio
async def test_summary_map_reduce():
    # 1. 模拟一个 LLM 客户端
    mock_llm = AsyncMock()
    
    # 定义模拟的 JSON 返回结构，满足 Schema 校验
    mock_llm.chat_json.return_value = {
        "title": "全局重构架构会",
        "date": "2026-06-09",
        "participants": ["开发专家", "架构师"],
        "topics": [],
        "decisions": ["决定使用并发重试兜底"],
        "next_steps": ["执行单测跑通流程"]
    }
    
    # 2. 实例化 Agent，注入 mock client
    agent = SummaryAgent(llm_client=mock_llm)
    
    # 3. 构造一个 5000 字的假转录文本（超过 3000 字阈值，触发 MapReduce）
    long_transcript = "测试数据" * 1250  # 1250 * 4 = 5000 chars
    
    from schemas import MeetingGraphState, JobConfig
    # 模拟 LangGraph State (使用 Pydantic 模型)
    state = MeetingGraphState(
        meeting_id="test-map-reduce-001",
        transcript_text=long_transcript,
        keyframes=[],
        job_config=JobConfig()
    )
    
    # 4. 执行 Agent 节点
    result = await agent.process(state)
    
    # 5. 断言验证
    # 验证返回结构是否符合预期
    assert "summary" in result
    summary = result["summary"]
    assert summary.title == "全局重构架构会"
    assert "决定使用并发重试兜底" in summary.decisions
    
    # 验证切分和调用次数
    # 5000 字符，按 3000 切分，overlap 200
    # Chunk 1: [0, 3000]
    # Chunk 2: [2800, 5000] (因为 start = 3000 - 200 = 2800, next end = 5800 > 5000)
    # 所以应该切出 2 个 Chunk，并发调 2 次 Map
    # 最后调 1 次 Reduce
    # 所以 LLM 总共被调用应该恰好等于 3 次
    assert mock_llm.chat_json.call_count == 3
    print("MapReduce 逻辑与并发调用次数验证通过！")

if __name__ == "__main__":
    asyncio.run(test_summary_map_reduce())
