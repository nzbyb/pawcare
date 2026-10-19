from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.agent import ChatRequest
from app.services import agent_service

router = APIRouter(tags=["智能助手"])


@router.post("/agent/chat", response_model=Response)
async def agent_chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = await agent_service.chat(db, current_user, data)
    return Response.success(data=result.model_dump())


@router.get("/agent/conversations", response_model=Response)
def list_agent_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = agent_service.list_conversations(db, current_user)
    return Response.success(
        data=[agent_service.conversation_payload(item) for item in conversations]
    )


@router.get("/agent/conversations/{conversation_id}", response_model=Response)
def get_agent_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    messages = agent_service.get_messages(db, current_user, conversation_id)
    return Response.success(
        data={
            "conversation_id": conversation_id,
            "messages": [agent_service.message_payload(item) for item in messages],
        }
    )
