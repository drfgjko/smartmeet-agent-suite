
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str = Field(..., description="任务状态: pending, processing, completed, failed")
    meeting_id: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    message: str
    meeting_id: str
