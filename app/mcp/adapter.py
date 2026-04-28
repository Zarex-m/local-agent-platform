from app.mcp.config import MCP_SERVERS
from app.mcp.client import list_mcp_tools_sync, call_mcp_tool_sync

def make_mcp_handler(server_name:str,tool_name:str):
    def handler(tool_input:dict)->dict:
        return call_mcp_tool_sync(
            server_name=server_name,
            tool_name=tool_name,
            arguments=tool_input,
        )
    return handler

def load_mcp_tools_to_registry() -> dict:
    registry_items = {}

    for server_name in MCP_SERVERS.keys():
        try:
            tools = list_mcp_tools_sync(server_name)
        except Exception as e:
            print(f"加载 MCP Server 失败：{server_name}，原因：{e}")
            continue

        for tool in tools:
            registry_name = f"mcp.{server_name}.{tool['name']}"

            registry_items[registry_name] = {
                "name": registry_name,
                "description": f"[MCP:{server_name}] {tool['description']}",
                "input_schema": tool["input_schema"],
                "risk_level": "medium",
                "handler": make_mcp_handler(
                    server_name=server_name,
                    tool_name=tool["name"],
                ),
            }

    return registry_items
