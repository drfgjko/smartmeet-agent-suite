# -*- coding: utf-8 -*-
"""
UnifiedLLMClient 与 create_llm_client 工厂方法的单元测试。
"""

from __future__ import annotations
import os
import pytest
from unittest import mock
from services.integrations.llm_client import create_llm_client, clean_and_parse_json, UnifiedLLMClient

def test_clean_and_parse_json():
    # 测试标准 JSON 解析
    assert clean_and_parse_json('{"key": "value"}') == {"key": "value"}

    # 测试 Markdown 格式的 JSON 代码块解析
    text_with_block = "```json\n{\n  \"hello\": \"world\"\n}\n```"
    assert clean_and_parse_json(text_with_block) == {"hello": "world"}

    # 测试前后夹杂额外说明文本的 JSON 段落提取解析
    text_with_extra = "Some explanations: {\"a\": 1, \"b\": 2} details."
    assert clean_and_parse_json(text_with_extra) == {"a": 1, "b": 2}

    # 测试非法的 JSON 文本，确保抛出异常
    with pytest.raises(Exception):
        clean_and_parse_json("invalid json text")


def test_create_llm_client_defaults():
    # 测试默认配置下缺失 API Key，确保 Fail-Fast 报错
    llm_vars = [
        "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL",
        "OPENAI_API_KEY", "MINIMAX_API_KEY", "MINIMAX_GROUP_ID", "MINIMAX_MODEL",
        "NOTEKING_LLM_BASE_URL", "NOTEKING_LLM_MODEL", "OPENAI_MODEL"
    ]
    with mock.patch.dict(os.environ, {}):
        for v in llm_vars:
            os.environ.pop(v, None)
        with pytest.raises(ValueError) as exc:
            create_llm_client()
        assert "未在环境变量中配置 LLM_API_KEY" in str(exc.value)


def test_create_llm_client_explicit():
    # 测试通过参数显式指定
    client = create_llm_client(api_key="explicit-key", base_url="http://explicit-url", model="explicit-model")
    assert client.api_key == "explicit-key"
    assert client.base_url == "http://explicit-url"
    assert client.model == "explicit-model"


def test_create_llm_client_env_priority():
    # 测试全新统一的 LLM_ 前缀环境变量的读取与优先级
    env = {
        "LLM_API_KEY": "new-key",
        "LLM_BASE_URL": "http://new-url",
        "LLM_MODEL": "new-model",
        "OPENAI_API_KEY": "legacy-key",
        "NOTEKING_LLM_BASE_URL": "http://legacy-url",
        "NOTEKING_LLM_MODEL": "legacy-model",
    }
    with mock.patch.dict(os.environ, env):
        client = create_llm_client()
        assert client.api_key == "new-key"
        assert client.base_url == "http://new-url"
        assert client.model == "new-model"


def test_create_llm_client_no_legacy_fallbacks():
    # 验证旧版本被弃用的变量已被彻底忽略，并在主 API Key 缺失时直接报错
    env = {
        "OPENAI_API_KEY": "legacy-openai-key",
        "NOTEKING_LLM_BASE_URL": "http://legacy-noteking-url",
        "NOTEKING_LLM_MODEL": "legacy-noteking-model",
        "LLM_API_KEY": "",  # 清空
        "LLM_BASE_URL": "",
        "LLM_MODEL": "",
    }
    with mock.patch.dict(os.environ, env):
        with pytest.raises(ValueError):
            create_llm_client()


def test_chat_stream_sync_uses_sync_client():
    client = UnifiedLLMClient(api_key="test-key", base_url="http://example.com", model="test-model")
    mock_stream = object()
    with mock.patch.object(client._sync_client.chat.completions, "create", return_value=mock_stream) as mocked_create:
        result = client.chat_stream_sync(
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.2,
            max_tokens=16,
            timeout=30,
        )
    assert result is mock_stream
    mocked_create.assert_called_once()
