MCP_SERVERS = {
    "bad": {
        "transport": "stdio",
        "command": ".venv/bin/python",
        "args": ["not_exist.py"],
        "env": None,
    },
    "time": {
        "transport": "stdio",
        "command": ".venv/bin/python",
        "args": ["-m", "mcp_server_time"],
        "env": None,
    },
}
