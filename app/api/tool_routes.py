from fastapi import APIRouter, HTTPException

from app.schemas.tasks import ToolDefinitionResponse, ToolUpdateRequest
from app.services import tool_service

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=list[ToolDefinitionResponse])
async def list_tools():
    return tool_service.list_tools()


@router.patch("/{tool_name}", response_model=ToolDefinitionResponse)
async def update_tool(tool_name: str, request: ToolUpdateRequest):
    tool = tool_service.update_tool_enabled(tool_name, request.enabled)

    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    return tool
