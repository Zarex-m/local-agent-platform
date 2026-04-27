from pydantic import BaseModel
from datetime import datetime

class TaskCreateRequest(BaseModel):
    task: str 

class TaskApproveRequest(BaseModel):
    approved: bool
    
class TaskResponse(BaseModel):
    id: int
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