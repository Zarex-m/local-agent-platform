from app.tools.builtin import (
    mock_tool,
    list_files,
    read_file,
    write_file,
    run_shell,
    http_request,
)

TOOL_REGISTRY = {
    "mock_tool": {
        "name": "mock_tool",
        "description": "这是一个模拟工具，不执行实际操作，适用于测试和占位",
        "input_schema": {},
        "risk_level": "low",
        "handler": mock_tool,
    },
    "list_files": {
        "name": "list_files",
        "description": "列出指定目录下的文件",
        "input_schema": {"path": "目录路径,默认是."},
        "risk_level": "low",
        "handler": list_files,
    },
    "read_file": {
        "name": "read_file",
        "description": "读取指定文件的内容",
        "input_schema": {"path": "文件路径"},
        "risk_level": "low",
        "handler": read_file,
    },
    "write_file": {
        "name": "write_file",
        "description": "写入内容到指定文件",
        "input_schema": {"path": "文件路径", "content": "要写入的内容"},
        "risk_level": "high",
        "handler": write_file,
    },
    "run_shell": {
        "name": "run_shell",
        "description": "执行本地shell命令，适用于运行测试、查看系统命令输出、执行项目脚本",
        "input_schema": {
            "command": "要执行的shell命令",
            "cwd": "命令执行的工作目录，默认是.",
            "timeout": "命令执行的超时时间，单位是秒，默认是30秒",
        },
        "risk_level": "high",
        "handler": run_shell,
    },
    "http_request": {
        "name": "http_request",
        "description": "发起 HTTP 请求，适用于访问 API、测试接口、获取网页或服务响应",
        "input_schema": {
            "method": "HTTP 方法，例如 GET、POST、PUT、DELETE，默认 GET",
            "url": "请求地址，必须是完整 URL",
            "headers": "请求头，默认是空对象",
            "params": "URL 查询参数，默认是空对象",
            "json": "JSON 请求体，POST/PUT/PATCH 时常用",
            "timeout": "超时时间，单位秒，默认 30",
        },
        "risk_level": "medium",
        "handler": http_request,
    },
}

try:
    from app.mcp.adapter import load_mcp_tools_to_registry

    TOOL_REGISTRY.update(load_mcp_tools_to_registry())
except Exception as e:
    print(f"加载 MCP 工具失败：{e}")


def get_tool_source(tool_name: str) -> str:
    return "mcp" if tool_name.startswith("mcp.") else "local"


def list_tool_definitions() -> list[dict]:
    tools = []

    for tool in TOOL_REGISTRY.values():
        name = tool.get("name", "")
        tools.append(
            {
                "name": name,
                "source": get_tool_source(name),
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema") or {},
                "risk_level": tool.get("risk_level", "unknown"),
                "enabled": tool.get("enabled", True),
            }
        )

    return tools


def set_tool_enabled(tool_name: str, enabled: bool) -> dict | None:
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return None

    tool["enabled"] = enabled
    return {
        "name": tool.get("name", tool_name),
        "source": get_tool_source(tool_name),
        "description": tool.get("description", ""),
        "input_schema": tool.get("input_schema") or {},
        "risk_level": tool.get("risk_level", "unknown"),
        "enabled": tool.get("enabled", True),
    }


def is_tool_enabled(tool_name: str) -> bool:
    tool = TOOL_REGISTRY.get(tool_name)
    return bool(tool and tool.get("enabled", True))


def get_tools_text() -> str:
    lines = []
    for tool in TOOL_REGISTRY.values():
        if not tool.get("enabled", True):
            continue

        lines.append(
            f"- {tool['name']}：{tool['description']}，参数：{tool['input_schema']}，风险等级：{tool['risk_level']}"
        )
    return "\n".join(lines)
