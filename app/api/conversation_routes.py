from fastapi import APIRouter, HTTPException

from app.schemas.tasks import ConversationResponse, MessageResponse, ConversationUpdateRequest
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/", response_model=list[ConversationResponse])
async def list_conversation_items(limit: int = 30):
    return conversation_service.list_conversations(limit)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_detail(conversation_id: int):
    conversation = conversation_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_message_items(conversation_id: int):
    conversation = conversation_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation_service.get_messages(conversation_id)

@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_api(conversation_id: int, request: ConversationUpdateRequest):
    conversation = conversation_service.update_conversation(
        conversation_id,
        title=request.title,
        summary=request.summary,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.delete("/{conversation_id}")
async def delete_conversation_api(conversation_id: int):
    ok = conversation_service.delete_conversation(conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}
