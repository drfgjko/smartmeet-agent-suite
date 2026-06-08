# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException
from schemas.task_schema import TaskStatusResponse
from services.core.task_service import TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
task_service = TaskService()

@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    轮询接口：获取异步任务的当前执行状态和最终产物
    """
    task = task_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task
