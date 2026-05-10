import sys

MCP_SERVERS = {
    "time": {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "mcp_server_time"],
        "env": None,
        "risk_level": "low",
        "tool_risk_levels": {},
    },
    "workspace": {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "mcp_servers.workspace_server"],
        "env": None,
        "risk_level": "medium",
        "tool_risk_levels": {
            "scan_files": "low",
            "copy_file": "high",
            "move_file": "high",
            "rename_file": "high",
            "write_markdown_report": "high",
            "read_workspace_file": "low"
        },
    },
}
