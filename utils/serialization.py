# -*- coding: utf-8 -*-
"""
序列化工具集合
"""
from typing import Any


def model_dump_if_needed(value: Any) -> Any:
    """
    如果值是 Pydantic 模型（有 model_dump 方法），则序列化为 dict；否则直接返回原值。

    Args:
        value: 待检查的值，可能是 Pydantic 模型实例或其他类型

    Returns:
        序列化后的 dict 或原始值
    """
    if value is not None and hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def serialize_agent_outputs(final_state: dict[str, Any]) -> dict[str, Any]:
    """
    从工作流最终状态中提取并序列化四个 Agent 的输出结果。

    四个 Agent 分别为：summary（摘要）、actions（行动项）、insights（洞察）、followup（跟进）。

    Args:
        final_state: meeting_workflow 完成后返回的最终状态字典

    Returns:
        包含四个 Agent 输出的字典，所有 Pydantic 模型已被序列化为 dict
    """
    return {
        "summary": model_dump_if_needed(final_state.get("summary")),
        "actions": model_dump_if_needed(final_state.get("actions")),
        "insights": model_dump_if_needed(final_state.get("insights")),
        "followup": model_dump_if_needed(final_state.get("followup")),
    }
