from app.storage import conversation_repository as conversation_repo


def list_conversations(limit: int = 30) -> list[dict]:
    return conversation_repo.list_conversations(limit)


def get_conversation(conversation_id: int) -> dict | None:
    return conversation_repo.get_conversation(conversation_id)


def get_messages(conversation_id: int):
    return conversation_repo.get_messages(conversation_id)


def update_conversation(
    conversation_id: int,
    title: str | None = None,
    summary: str | None = None,
) -> dict | None:
    return conversation_repo.update_conversation(
        conversation_id,
        title=title,
        summary=summary,
    )


def delete_conversation(conversation_id: int) -> bool:
    return conversation_repo.delete_conversation(conversation_id)
