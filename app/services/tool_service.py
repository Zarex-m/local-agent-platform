from app.tools.registry import list_tool_definitions, set_tool_enabled


def list_tools() -> list[dict]:
    return list_tool_definitions()


def update_tool_enabled(tool_name: str, enabled: bool) -> dict | None:
    return set_tool_enabled(tool_name, enabled)
