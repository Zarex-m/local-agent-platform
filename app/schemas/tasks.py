from pydantic import BaseModel, Field
from datetime import datetime

class TaskCreateRequest(BaseModel):
    task: str
    conversation_id: int | None = None
    attachment_paths: list[str] = Field(default_factory=list)


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
    cancel_requested: bool
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

class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None

class ToolDefinitionResponse(BaseModel):
    name: str
    source: str
    description: str
    input_schema: dict
    risk_level: str
    enabled: bool


class ToolUpdateRequest(BaseModel):
    enabled: bool


class UploadedFileResponse(BaseModel):
    filename: str
    stored_name: str
    path: str
    display_path: str
    size: int
    content_type: str | None = None
