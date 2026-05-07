from fastapi import APIRouter, HTTPException

from app.schemas.tasks import ConversationResponse, MessageResponse, ConversationUpdateRequest
from app.storage.conversation_repository import update_conversation,delete_conversation
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

@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_api(conversation_id: int, request: ConversationUpdateRequest):
    conversation = update_conversation(
        conversation_id,
        title=request.title,
        summary=request.summary,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.delete("/{conversation_id}")
async def delete_conversation_api(conversation_id: int):
    ok = delete_conversation(conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}
