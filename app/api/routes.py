from fastapi import APIRouter,HTTPException
from app.services.agent_service import run_task,approve_task
from app.schemas.tasks import TaskCreateRequest,TaskApproveRequest,TaskResponse,StepLogResponse
from app.storage.task_repository import get_task,get_step_logs,list_tasks,get_tool_calls

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/")
async def submit_task(request: TaskCreateRequest):
    result=run_task(request.task)
    return result

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_detail(task_id:int):
    task=get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404,detail="Task not found")
    
    return task
    
@router.get("/{task_id}/logs", response_model=list[StepLogResponse])
async def get_task_logs(task_id: int):
    return get_step_logs(task_id)
    
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
    
@router.get("/",response_model=list[TaskResponse])
async def list_task_items(limit:int=20):
    return list_tasks(limit)

@router.get("/{task_id}/tool-calls")
async def get_task_tool_calls(task_id: int):
    return get_tool_calls(task_id)
