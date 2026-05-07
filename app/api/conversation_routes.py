from fastapi import APIRouter, HTTPException

from app.schemas.tasks import ConversationResponse, MessageResponse
from app.storage.conversation_repository import (
    get_conversation,
    get_messages,
    list_conversations,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/", response_model=list[ConversationResponse])
async def list_conversation_items(limit: int = 30):
    return list_conversations(limit)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_detail(conversation_id: int):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_message_items(conversation_id: int):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return get_messages(conversation_id)
