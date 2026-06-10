from fastapi import APIRouter, HTTPException, Request
from schemas.task_schema import TaskStatusResponse
from arq.jobs import Job, JobStatus

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(request: Request, task_id: str):
    redis_pool = getattr(request.app.state, "redis", None)
    if not redis_pool:
        raise HTTPException(status_code=500, detail="Redis pool not initialized")

    job = Job(task_id, redis_pool)
    status = await job.status()

    if status == JobStatus.not_found:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    result_dict = None
    error_msg = None

    if status == JobStatus.complete:
        try:
            result_dict = await job.result()
        except Exception as e:
            error_msg = str(e)

    return TaskStatusResponse(
        task_id=task_id,
        status=status.value,
        meeting_id=None,
        result=result_dict,
        error=error_msg,
    )

@router.delete("/{task_id}")
async def abort_task(request: Request, task_id: str):
    redis_pool = getattr(request.app.state, "redis", None)
    if not redis_pool:
        raise HTTPException(status_code=500, detail="Redis pool not initialized")

    job = Job(task_id, redis_pool)
    status = await job.status()
    if status == JobStatus.not_found:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if status in [JobStatus.queued, JobStatus.in_progress]:
        success = await job.abort()
        if success:
            return {"status": "success", "message": "Task aborted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to abort task")
    return {"status": "skipped", "message": f"Task already in status: {status.value}"}
