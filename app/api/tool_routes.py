from fastapi import APIRouter, HTTPException

from app.schemas.tasks import ToolDefinitionResponse, ToolUpdateRequest
from app.tools.registry import list_tool_definitions, set_tool_enabled

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=list[ToolDefinitionResponse])
async def list_tools():
    return list_tool_definitions()


@router.patch("/{tool_name}", response_model=ToolDefinitionResponse)
async def update_tool(tool_name: str, request: ToolUpdateRequest):
    tool = set_tool_enabled(tool_name, request.enabled)

    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    return tool
