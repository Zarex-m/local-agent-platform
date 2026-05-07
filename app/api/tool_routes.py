from fastapi import APIRouter

from app.schemas.tasks import ToolDefinitionResponse
from app.tools.registry import TOOL_REGISTRY

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=list[ToolDefinitionResponse])
async def list_tools():
    tools = []

    for tool in TOOL_REGISTRY.values():
        name = tool.get("name", "")
        tools.append(
            {
                "name": name,
                "source": "mcp" if name.startswith("mcp.") else "local",
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema") or {},
                "risk_level": tool.get("risk_level", "unknown"),
                "enabled": tool.get("enabled", True),
            }
        )

    return tools
