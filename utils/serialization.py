# -*- coding: utf-8 -*-
"""
序列化工具集合

层间契约约定：
- Service 层（ReportComposer / ReportDelivery 等）统一接收 Pydantic 对象，不接受裸 dict。
- dump_outputs_for_json 仅用于最终 API 响应体或 WebSocket 推送，严禁在 Service 层调用链中间使用。
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


def dump_outputs_for_json(final_state: dict[str, Any]) -> dict[str, Any]:
    """
    将工作流最终状态中的 Pydantic Agent 输出序列化为 dict，专用于 JSON 响应体组装。

    !! 使用限制 !!
    - 允许：API 响应体组装、WebSocket/SSE 事件推送
    - 禁止：在 Service 层调用链中间使用（Service 层统一接收 Pydantic 对象）

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
