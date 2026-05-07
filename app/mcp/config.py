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
}
