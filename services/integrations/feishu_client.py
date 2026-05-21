# -*- coding: utf-8 -*-
"""飞书 Open API 集成客户端 - 消息推送和任务管理"""

from __future__ import annotations
import os
import time
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
        self._client = httpx.AsyncClient(timeout=30.0)
        self._tenant_token = ""
        self._token_expires_at = 0
        self._enabled = bool((self.app_id and self.app_secret) or self.webhook_url)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def _get_tenant_token(self) -> str:
        if self._tenant_token and time.time() < self._token_expires_at:
            return self._tenant_token
        if not (self.app_id and self.app_secret):
            return ""
        resp = await self._client.post(
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
            logger.warning("Feishu webhook not configured, skipping")
            return False
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": content}],
            },
        }
        resp = await self._client.post(self.webhook_url, json=card)
        data = resp.json()
        success = data.get("code", -1) == 0
        if success:
            logger.info(f"Feishu webhook message sent: {title}")
        else:
            logger.error(f"Feishu webhook failed: {data}")
        return success

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_message(self, receive_id: str, content: str, receive_id_type: str = "chat_id", msg_type: str = "text") -> dict[str, Any]:
        token = await self._get_tenant_token()
        if not token:
            return {"success": False, "error": "No token"}
        resp = await self._client.post(
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
        resp = await self._client.post(
            f"{self.BASE_URL}/task/v2/tasks",
            headers={"Authorization": f"Bearer {token}"},
            json=task_body,
        )
        data = resp.json()
        task_id = data.get("data", {}).get("task", {}).get("id", "")
        logger.info(f"Created Feishu task: {task_id} - {summary}")
        return {"task_id": task_id, "data": data}

    async def send_meeting_summary(self, title: str, summary_md: str, action_items_md: str, insights_md: str) -> bool:
        content = (
            f"**会议主题**: {title}\n\n"
            f"---\n\n"
            f"**📋 会议纪要**\n{summary_md}\n\n"
            f"---\n\n"
            f"**✅ 待办事项**\n{action_items_md}\n\n"
            f"---\n\n"
            f"**📊 会议洞察**\n{insights_md}"
        )
        return await self.send_webhook_message(title=f"📝 会议纪要 | {title}", content=content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def upload_file(self, file_path: str | Path, file_type: str = "pdf") -> str:
        """
        上传文件到飞书
        API 文档: https://open.feishu.cn/document/uAjLw4COyYjL3gDM/uMTNz4yN1MjLzUzM
        """
        from pathlib import Path
        token = await self._get_tenant_token()
        if not token:
            logger.warning("Feishu token is not available, skipping upload")
            return ""
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return ""
            
        url = f"{self.BASE_URL}/im/v1/files"
        headers = {"Authorization": f"Bearer {token}"}
        
        # Read bytes to avoid file open encoding checks
        file_bytes = path.read_bytes()
        
        data = {
            "file_type": file_type,
            "file_name": path.name,
        }
        files = {
            "file": (path.name, file_bytes, "application/octet-stream")
        }
        
        try:
            resp = await self._client.post(url, headers=headers, data=data, files=files)
            res = resp.json()
            if res.get("code") == 0:
                file_key = res.get("data", {}).get("file_key", "")
                logger.info(f"Uploaded file {path.name} to Feishu, file_key: {file_key}")
                return file_key
            else:
                logger.error(f"Feishu upload file failed: {res}")
                return ""
        except Exception as e:
            logger.exception(f"Error during Feishu upload: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_file(self, receive_id: str, file_key: str, receive_id_type: str = "chat_id") -> bool:
        """
        通过 API 发送文件消息给指定接收者
        API 文档: https://open.feishu.cn/document/server-docs/im-v1/message/create
        """
        import json
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
            resp = await self._client.post(url, headers=headers, params=params, json=body)
            res = resp.json()
            success = res.get("code") == 0
            if success:
                logger.info(f"Successfully sent Feishu file message to {receive_id}")
            else:
                logger.error(f"Feishu send file message failed: {res}")
            return success
        except Exception as e:
            logger.exception(f"Error during Feishu send file: {e}")
            return False

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
