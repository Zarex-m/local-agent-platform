from fastapi import APIRouter,HTTPException,BackgroundTasks
from app.services.agent_service import (
    run_task,
    approve_task,
    run_task_background,
    create_task_job,
)
from app.schemas.tasks import TaskCreateRequest,TaskApproveRequest,TaskResponse,StepLogResponse
from app.storage.task_repository import get_task,get_step_logs,list_tasks,get_tool_calls
import asyncio
import json
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/")
async def submit_task(request: TaskCreateRequest,background_tasks: BackgroundTasks):
    payload = create_task_job(request.task, request.conversation_id)

    background_tasks.add_task(
    run_task_background,
    payload["task_id"],
    payload["thread_id"],
    request.task,
    payload["conversation_id"],
)
    
    return payload

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

def sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.get("/{task_id}/events")
async def stream_task_events(task_id: int):
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        last_log_id = 0
        last_tool_call_id = 0
        last_status = None
        last_final_response = None

        while True:
            task = get_task(task_id)

            if task is None:
                yield sse_event("error", {"message": "Task not found"})
                return

            if task.status != last_status:
                last_status = task.status
                yield sse_event(
                    "task",
                    {
                        "id": task.id,
                        "status": task.status,
                        "final_response": task.final_response,
                        "approval_required": task.approval_required,
                        "approval_reason": task.approval_reason,
                    },
                )

            current_final_response = task.final_response or ""
            if current_final_response != last_final_response:
                last_final_response = current_final_response
                yield sse_event(
                    "final_response",
                    {
                        "id": task.id,
                        "status": task.status,
                        "final_response": current_final_response,
                    },
                )

            logs = get_step_logs(task_id)
            for log in logs:
                if log.id > last_log_id:
                    last_log_id = log.id
                    yield sse_event(
                        "log",
                        {
                            "id": log.id,
                            "node": log.node,
                            "status": log.status,
                            "message": log.message,
                            "created_at": log.created_at,
                        },
                    )

            tool_calls = get_tool_calls(task_id)
            for tool_call in tool_calls:
                if tool_call["id"] > last_tool_call_id:
                    last_tool_call_id = tool_call["id"]
                    yield sse_event("tool_call", tool_call)

            if task.status in {"completed", "failed", "rejected"}:
                yield sse_event("done", {"task_id": task_id, "status": task.status})
                return

            await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
