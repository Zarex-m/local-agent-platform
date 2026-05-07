from pydantic import BaseModel
from datetime import datetime

class TaskCreateRequest(BaseModel):
    task: str
    conversation_id: int | None = None


class TaskApproveRequest(BaseModel):
    approved: bool
    
class TaskResponse(BaseModel):
    id: int
    conversation_id: int | None
    thread_id: str
    task: str
    status: str
    selected_tool: str | None
    final_response: str | None
    approval_required: bool | None
    approval_reason: str | None
    created_at: datetime
    updated_at: datetime
    
class StepLogResponse(BaseModel):
    id: int
    task_id: int
    node: str
    status: str
    message: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    title: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime
    latest_task_id: int | None
    latest_task_title: str | None
    latest_task_status: str | None


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    task_id: int | None
    role: str
    content: str
    created_at: datetime
