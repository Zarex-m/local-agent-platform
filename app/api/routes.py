from fastapi import APIRouter,HTTPException
from app.services.agent_service import run_task,approve_task
from app.schemas.tasks import TaskCreateRequest,TaskApproveRequest
from app.storage.task_repository import get_task,get_step_logs,list_tasks
router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/")
async def submit_task(request: TaskCreateRequest):
    result=run_task(request.task)
    return result

@router.get("/{task_id}")
async def get_task_detail(task_id:int):
    task=get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404,detail="Task not found")
    
    return {
        "id": task.id,
        "thread_id": task.thread_id,
        "task": task.task,
        "status": task.status,
        "selected_tool": task.selected_tool,
        "final_response": task.final_response,
        "approval_required": task.approval_required,
        "approval_reason": task.approval_reason,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    
@router.get("/{task_id}/logs")
async def get_task_logs(task_id: int):
    logs=get_step_logs(task_id)
    return [
        {
            "id": log.id,
            "task_id": log.task_id,
            "node": log.node,
            "status": log.status,
            "message": log.message,
            "created_at": log.created_at,
        }
        for log in logs
    ]
    
@router.post("/{task_id}/approve")
async def approve_task_api(task_id:int,request:TaskApproveRequest):
    task=get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404,detail="task is not found")
    if task.thread_id is None:
        raise HTTPException(status_code=400,detail="task thread_id is missing")
    thread_id=task.thread_id
    result=approve_task(task_id,thread_id,request.approved)
    return result
    
@router.get("/")
async def list_task_items(limit:int=20):
    tasks=list_tasks(limit)
    return [
        {
            "id": task.id,
            "thread_id": task.thread_id,
            "task": task.task,
            "status": task.status,
            "selected_tool": task.selected_tool,
            "final_response": task.final_response,
            "approval_required": task.approval_required,
            "approval_reason": task.approval_reason,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        for task in tasks
    ]