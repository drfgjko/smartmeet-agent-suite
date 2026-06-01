# -*- coding: utf-8 -*-
"""
任务状态机服务，封装 SQLite 增删改查
"""
import json
from typing import Any, Optional
from models.task import SessionLocal, TaskRecord
from schemas.task_schema import TaskStatusResponse

class TaskService:
    def create_task(self, task_id: str, meeting_id: Optional[str] = None) -> TaskRecord:
        """创建一个全新的 pending 任务"""
        with SessionLocal() as db:
            task = TaskRecord(task_id=task_id, status="pending", meeting_id=meeting_id)
            db.add(task)
            db.commit()
            db.refresh(task)
            return task
            
    def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        result: Optional[dict[str, Any]] = None, 
        error: Optional[str] = None
    ) -> None:
        """更新任务状态及产物"""
        with SessionLocal() as db:
            task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            if task:
                task.status = status
                if result is not None:
                    task.result_json = json.dumps(result, ensure_ascii=False)
                if error is not None:
                    task.error_msg = error
                db.commit()

    def get_task_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """查询任务状态并返回 Schema 对象"""
        with SessionLocal() as db:
            task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            if not task:
                return None
            
            result_dict = json.loads(task.result_json) if task.result_json else None
            
            return TaskStatusResponse(
                task_id=task.task_id,
                status=task.status,
                meeting_id=task.meeting_id,
                result=result_dict,
                error=task.error_msg,
                created_at=task.created_at,
                updated_at=task.updated_at
            )
