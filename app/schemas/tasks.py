from pydantic import BaseModel

class TaskCreateRequest(BaseModel):
    task: str 

class TaskApproveRequest(BaseModel):
    approved: bool