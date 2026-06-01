from __future__ import annotations


def _state_value(state: object, key: str, default):
    if hasattr(state, "model_fields_set"):
        if key in state.model_fields_set:
            value = getattr(state, key)
            return default if value is None else value
        return default
    raise TypeError(f"Expected Pydantic model, got {type(state).__name__}")