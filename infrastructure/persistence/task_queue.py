# -*- coding: utf-8 -*-
"""
纯 Python 轻量级异步任务总线
"""
import asyncio
from typing import Any, Coroutine
from loguru import logger
from .task_service import TaskService
from services.delivery import WebhookService

class TaskQueue:
    def __init__(self):
        self.task_service = TaskService()
        self.webhook_service = WebhookService()

    async def execute_task(
        self, 
        task_id: str, 
        coro: Coroutine[Any, Any, Any],
        webhook_urls: list[str] = None
    ) -> None:
        """
        后台执行协程任务的包装器，负责状态机流转与异常捕获
        此函数可以直接放入 FastAPI 的 BackgroundTasks 或 asyncio.create_task 中执行
        """
        try:
            # 1. 更新状态为 processing
            self.task_service.update_task_status(task_id, status="processing")
            logger.info(f"[TaskQueue] Task {task_id} started processing.")

            # 2. 执行真正的耗时任务
            result = await coro
            
            # 由于部分返回模型可能包含 Pydantic 对象，确保转换为可序列化的 dict
            if hasattr(result, "model_dump"):
                result_dict = result.model_dump()
            elif isinstance(result, dict):
                result_dict = result
            else:
                result_dict = {"data": str(result)}
            
            # 3. 任务成功完成
            self.task_service.update_task_status(task_id, status="completed", result=result_dict)
            logger.info(f"[TaskQueue] Task {task_id} completed successfully.")

            # 4. 触发 Webhook
            if webhook_urls:
                webhook_payload = {
                    "event": "task_completed",
                    "task_id": task_id,
                    "status": "completed",
                    "result": result_dict
                }
                await self.webhook_service.dispatch(webhook_urls, webhook_payload)

        except Exception as e:
            logger.exception(f"[TaskQueue] 任务 {task_id} 执行失败: {e}")
            self.task_service.update_task_status(task_id, status="failed", error=str(e))
            
            if webhook_urls:
                webhook_payload = {
                    "event": "task_failed",
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e)
                }
                await self.webhook_service.dispatch(webhook_urls, webhook_payload)

# 模块级单例
task_queue = TaskQueue()
