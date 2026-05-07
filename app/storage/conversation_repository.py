from datetime import datetime

from sqlalchemy import select

from app.storage.database import Conversation, Message, SessionLocal, Task


def _conversation_payload(db, conversation: Conversation) -> dict:
    latest_task_stmt = (
        select(Task)
        .where(Task.conversation_id == conversation.id)
        .order_by(Task.id.desc())
        .limit(1)
    )
    latest_task = db.execute(latest_task_stmt).scalar_one_or_none()

    return {
        "id": conversation.id,
        "title": conversation.title,
        "summary": conversation.summary,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "latest_task_id": latest_task.id if latest_task else None,
        "latest_task_title": latest_task.task if latest_task else None,
        "latest_task_status": latest_task.status if latest_task else None,
    }

#创建会话
def create_conversation(title: str | None = None) -> int:
    db = SessionLocal()
    try:
        item = Conversation(title=title)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id
    finally:
        db.close()


def list_conversations(limit: int = 30) -> list[dict]:
    db = SessionLocal()
    try:
        stmt = (
            select(Conversation)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .limit(limit)
        )
        conversations = db.execute(stmt).scalars().all()
        return [_conversation_payload(db, item) for item in conversations]
    finally:
        db.close()


def get_conversation(conversation_id: int) -> dict | None:
    db = SessionLocal()
    try:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        conversation = db.execute(stmt).scalar_one_or_none()
        if conversation is None:
            return None

        return _conversation_payload(db, conversation)
    finally:
        db.close()

#添加信息到会话中
def append_message(
    conversation_id: int,
    role: str,
    content: str,
    task_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        item = Message(
            conversation_id=conversation_id,
            task_id=task_id,
            role=role,
            content=content,
        )
        db.add(item)

        conversation = db.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(item)
        return item.id
    finally:
        db.close()

#获取最近的信息
def get_recent_messages(conversation_id: int, limit: int = 10) -> list[Message]:
    db = SessionLocal()
    try:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        messages = db.execute(stmt).scalars().all()
        return list(reversed(messages))
    finally:
        db.close()


def get_messages(conversation_id: int) -> list[Message]:
    db = SessionLocal()
    try:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
        return db.execute(stmt).scalars().all()
    finally:
        db.close()
