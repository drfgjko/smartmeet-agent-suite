# -*- coding: utf-8 -*-
"""
通用 Webhook 推送服务

将标准化 JSON payload POST 到用户在 JobConfig.webhook_urls 中配置的外部 URL 列表。
覆盖钉钉、企业微信、Slack 或任何能接收 JSON POST 的自定义系统。

设计约束:
- 每个 URL 独立超时控制（默认 10s），单个失败不阻塞其他推送
- 默认关闭（webhook_urls 为空列表时不触发）
- 遵守 AGENTS.md 编码规范：ensure_ascii=False
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger

from schemas.meeting_schemas import DeliveryResult


class WebhookService:
    """通用 Webhook 推送服务"""

    async def dispatch(
        self,
        urls: list[str],
        payload: dict[str, Any],
        timeout: float = 10.0,
    ) -> list[DeliveryResult]:
        """
        向所有目标 URL 推送 payload。

        Args:
            urls: 目标 Webhook URL 列表
            payload: 标准化 JSON 数据
            timeout: 单次推送超时（秒）

        Returns:
            每个 URL 的推送结果列表
        """
        if not urls:
            return []

        results: list[DeliveryResult] = []
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        async with httpx.AsyncClient(timeout=timeout) as client:
            for url in urls:
                result = DeliveryResult(channel="webhook", targets=[url])
                try:
                    resp = await client.post(
                        url,
                        content=payload_bytes,
                        headers={"Content-Type": "application/json; charset=utf-8"},
                    )
                    if resp.status_code < 400:
                        result.success = True
                        logger.info(f"[WebhookService] 推送成功: {url} (HTTP {resp.status_code})")
                    else:
                        result.success = False
                        result.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        logger.warning(f"[WebhookService] 推送失败: {url} - {result.error}")
                except httpx.TimeoutException:
                    result.success = False
                    result.error = f"超时 ({timeout}s)"
                    logger.warning(f"[WebhookService] 推送超时: {url}")
                except Exception as e:
                    result.success = False
                    result.error = str(e)
                    logger.error(f"[WebhookService] 推送异常: {url} - {e}")
                results.append(result)

        return results
