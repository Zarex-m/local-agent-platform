from app.storage.conversation_repository import (
    create_conversation,
    append_message,
    get_recent_messages,
)


def build_conversation_context(conversation_id: int | None, limit: int = 10) -> str:
    if conversation_id is None:
        return ""

    messages = get_recent_messages(conversation_id, limit)
    if not messages:
        return ""

    lines = []

    for message in messages:
        role = "用户" if message.role == "user" else "助手"
        lines.append(f"{role}: {message.content}")

    return "\n".join(lines)
