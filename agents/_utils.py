# -*- coding: utf-8 -*-
"""
Agent 层内部工具函数
"""

from __future__ import annotations


def _state_value(state: object, key: str, default):
    if hasattr(state, key):
        value = getattr(state, key)
        return default if value is None else value
    if isinstance(state, dict):
        return state.get(key, default)
    return default