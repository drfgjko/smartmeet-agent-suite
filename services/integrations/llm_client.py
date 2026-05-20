# -*- coding: utf-8 -*-
"""
统一 LLM 客户端 - 支持 OpenAI, DeepSeek, MiniMax, Cloudflare Workers AI 等所有兼容 OpenAI SDK 的大模型。
提供用于 Agent 的异步客户端（AsyncOpenAI）以及用于生成文档引擎的同步客户端（OpenAI）。
"""

from __future__ import annotations
import os
import json
from typing import Any
from loguru import logger
from openai import OpenAI, AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

def clean_and_parse_json(text: str) -> dict:
    """辅助函数：解析文本中的 JSON，支持带 Markdown 代码块或额外文字描述的脏 JSON 解析"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试通过大括号定位 JSON 边界
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        raise

class UnifiedLLMClient:
    """
    统一大模型客户端，支持 OpenAI 兼容格式的所有 API 接口。
    提供面向 Agent 的异步方法（chat, chat_json）和面向文档/思维导图引擎的同步方法（chat_sync, chat_json_sync）。
    """
    def __init__(self, api_key: str, base_url: str | None = None, model: str = "gpt-4o-mini", **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        # 若配置了 MiniMax Group ID，则自动构建对应 Header
        headers = kwargs.pop("default_headers", {}) or {}
        group_id = kwargs.pop("group_id", None) or os.getenv("MINIMAX_GROUP_ID")
        if group_id:
            headers["x-minimax-group-id"] = group_id
            logger.info(f"使用 MiniMax 团队 ID: {group_id}")

        self._async_client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers, **kwargs)
        self._sync_client = OpenAI(api_key=api_key, base_url=base_url, default_headers=headers, **kwargs)
        logger.info(f"统一大模型客户端初始化成功 (模型: {self.model}, 接口端点: {self.base_url or 'OpenAI 官方默认'})")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def chat(self, messages: list[dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, response_format: dict | None = None) -> str:
        """异步文本生成"""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        response = await self._async_client.chat.completions.create(**payload)
        content = response.choices[0].message.content
        return content or ""

    async def chat_json(self, messages: list[dict[str, str]], temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """异步结构化 JSON 响应生成，内置自动降级清洗处理"""
        try:
            text = await self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.warning(f"异步请求指定 json_object 失败，自动退化至普通文本流聊天并解析: {e}")
            text = await self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return clean_and_parse_json(text)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def chat_sync(self, messages: list[dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, response_format: dict | None = None) -> str:
        """同步文本生成（用于非异步模块，如 PDF/思维导图引擎生成流水线）"""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        response = self._sync_client.chat.completions.create(**payload)
        content = response.choices[0].message.content
        return content or ""

    def chat_json_sync(self, messages: list[dict[str, str]], temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """同步结构化 JSON 响应生成，内置自动降级清洗处理"""
        try:
            text = self.chat_sync(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.warning(f"同步请求指定 json_object 失败，自动退化至普通文本流聊天并解析: {e}")
            text = self.chat_sync(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return clean_and_parse_json(text)

    async def close(self):
        """关闭异步连接池"""
        await self._async_client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


def create_llm_client(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    **kwargs
) -> UnifiedLLMClient:
    """
    大模型客户端统一工厂初始化方法。
    优先级排列：
    1. 显式参数传递
    2. 环境变量 (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL)
    """
    resolved_api_key = api_key or os.getenv("LLM_API_KEY")
    resolved_base_url = base_url or os.getenv("LLM_BASE_URL")
    resolved_model = model or os.getenv("LLM_MODEL")

    if not resolved_api_key:
        raise ValueError("未在环境变量中配置 LLM_API_KEY 且未显式传入 api_key 参数。")

    return UnifiedLLMClient(
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        model=resolved_model or "gpt-4o-mini",
        **kwargs
    )
