# -*- coding: utf-8 -*-
"""飞书 Open API 集成客户端 - 消息推送和任务管理"""

from __future__ import annotations
import os
import time
import json
from pathlib import Path
from typing import Any
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

class FeishuClient:
    """
    飞书开放平台 API 客户端

    职责:
    - 发送群消息（推送会议纪要）
    - 创建任务（同步待办事项）
    - Webhook 机器人消息

    API 文档: https://open.feishu.cn/document/home/index
    """
    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id=None, app_secret=None, webhook_url=None):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "")
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        self.receive_id = os.getenv("FEISHU_RECEIVE_ID", os.getenv("FEISHU_CHAT_ID", ""))
        self._client = None
        self._tenant_token = ""
        self._token_expires_at = 0
        self._enabled = bool((self.app_id and self.app_secret) or self.webhook_url)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def _get_tenant_token(self) -> str:
        if self._tenant_token and time.time() < self._token_expires_at:
            return self._tenant_token
        if not (self.app_id and self.app_secret):
            return ""
        resp = await self._get_client().post(
            f"{self.BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        self._tenant_token = data.get("tenant_access_token", "")
        self._token_expires_at = time.time() + data.get("expire", 7200) - 300
        return self._tenant_token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_webhook_message(self, title: str, content: str, msg_type: str = "interactive") -> bool:
        if not self.webhook_url:
            logger.warning("未配置飞书 Webhook 链接，跳过发送")
            return False
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": content}],
            },
        }
        resp = await self._get_client().post(self.webhook_url, json=card)
        data = resp.json()
        success = data.get("code", -1) == 0
        if success:
            logger.info(f"通过 Webhook 成功发送飞书消息: {title}")
        else:
            logger.error(f"飞书 Webhook 调用失败: {data}")
        return success

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_message(self, receive_id: str, content: str, receive_id_type: str = "chat_id", msg_type: str = "text") -> dict[str, Any]:
        token = await self._get_tenant_token()
        if not token:
            return {"success": False, "error": "No token"}
        resp = await self._get_client().post(
            f"{self.BASE_URL}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json={"receive_id": receive_id, "msg_type": msg_type, "content": content if isinstance(content, str) else str(content)},
        )
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_task(self, summary: str, description: str = "", due_timestamp: int | None = None, assignee_ids: list[str] | None = None) -> dict[str, Any]:
        token = await self._get_tenant_token()
        if not token:
            return {"success": False, "error": "No token"}
        task_body = {"summary": summary, "description": description or f"来源：会议助手自动创建"}
        if due_timestamp:
            task_body["due"] = {"timestamp": str(due_timestamp), "is_all_day": True}
        resp = await self._get_client().post(
            f"{self.BASE_URL}/task/v2/tasks",
            headers={"Authorization": f"Bearer {token}"},
            json=task_body,
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error(f"创建飞书任务失败: {data}")
            return {"task_id": "", "data": data, "error": data.get("msg")}
            
        task_id = data.get("data", {}).get("task", {}).get("guid", data.get("data", {}).get("task", {}).get("id", ""))
        logger.info(f"成功创建飞书任务: {task_id} - {summary}")
        return {"task_id": task_id, "data": data}

    async def send_meeting_summary(self, title: str, summary_md: str, action_items_md: str, insights_md: str) -> bool:
        import re
        def _clean_feishu_md(text: str) -> str:
            if not text:
                return ""
            # 将 markdown 的 # 标题语法转换为飞书卡片支持的加粗
            text = re.sub(r'^(#{1,6})\s+(.+)$', r'**\2**', text, flags=re.MULTILINE)
            return text.strip()

        content = (
            f"**🎯 会议主题**: {title}\n\n"
            f"---\n\n"
            f"**📋 会议纪要**\n{_clean_feishu_md(summary_md)}\n\n"
            f"---\n\n"
            f"**✅ 待办事项**\n{_clean_feishu_md(action_items_md)}\n\n"
            f"---\n\n"
            f"**📊 会议洞察**\n{_clean_feishu_md(insights_md)}"
        )
        
        # 优先使用 Webhook 发送
        if self.webhook_url:
            return await self.send_webhook_message(title=f"📝 会议纪要 | {title}", content=content)
            
        # 如果没有 Webhook 但有 receive_id，则通过开放平台机器人 API 发送卡片
        if self.receive_id:
            card_data = {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": f"📝 会议纪要 | {title}"}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": content}],
            }
            res = await self.send_message(
                receive_id=self.receive_id, 
                content=json.dumps(card_data, ensure_ascii=False), 
                msg_type="interactive"
            )
            success = res.get("code") == 0
            if not success:
                logger.error(f"飞书机器人 API 发送卡片失败: {res}")
            else:
                logger.info(f"成功通过飞书机器人 API 向 {self.receive_id} 发送总结卡片")
            return success
            
        logger.warning("未配置 Webhook 链接也未配置 Receive_ID，跳过发送会议总结卡片")
        return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def upload_file(self, file_path: str | Path, file_type: str = "pdf") -> str:
        """
        上传文件到飞书
        API 文档: https://open.feishu.cn/document/uAjLw4COyYjL3gDM/uMTNz4yN1MjLzUzM
        """
        token = await self._get_tenant_token()
        if not token:
            logger.warning("未配置飞书 Token，跳过文件上传")
            return ""
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"找不到需要上传的飞书文件: {file_path}")
            return ""
            
        url = f"{self.BASE_URL}/im/v1/files"
        headers = {"Authorization": f"Bearer {token}"}
        
        data = {
            "file_type": file_type,
            "file_name": path.name,
        }
        
        try:
            with open(path, "rb") as f:
                files = {
                    "file": (path.name, f, "application/octet-stream")
                }
                resp = await self._get_client().post(url, headers=headers, data=data, files=files)
            
            res = resp.json()
            if res.get("code") == 0:
                file_key = res.get("data", {}).get("file_key", "")
                logger.info(f"成功将文件 {path.name} 上传至飞书，文件 Key: {file_key}")
                return file_key
            else:
                logger.error(f"飞书上传文件失败: {res}")
                return ""
        except Exception as e:
            logger.exception(f"上传至飞书时发生异常: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_file(self, receive_id: str, file_key: str, receive_id_type: str = "chat_id") -> bool:
        """
        通过 API 发送文件消息给指定接收者
        API 文档: https://open.feishu.cn/document/server-docs/im-v1/message/create
        """
        token = await self._get_tenant_token()
        if not token:
            return False
        url = f"{self.BASE_URL}/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"receive_id_type": receive_id_type}
        content_str = json.dumps({"file_key": file_key}, ensure_ascii=False)
        
        body = {
            "receive_id": receive_id,
            "msg_type": "file",
            "content": content_str,
        }
        try:
            resp = await self._get_client().post(url, headers=headers, params=params, json=body)
            res = resp.json()
            success = res.get("code") == 0
            if success:
                logger.info(f"成功向 {receive_id} 发送飞书文件消息")
            else:
                logger.error(f"发送飞书文件消息失败: {res}")
            return success
        except Exception as e:
            logger.exception(f"发送飞书文件消息时发生异常: {e}")
            return False

    async def close(self):
        if self._client is not None:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
