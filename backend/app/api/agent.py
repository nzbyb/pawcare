import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.agent import ChatRequest
from app.services import agent_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["智能助手"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/agent/chat", response_model=Response)
async def agent_chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = await agent_service.chat(db, current_user, data)
    return Response.success(data=result.model_dump())


@router.post("/agent/chat/stream")
async def agent_chat_stream(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 校验和模型配置检查放在返回流之前，失败时仍是普通 JSON 错误。
    turn, llm = agent_service.prepare_stream(db, current_user, data)

    async def event_stream():
        try:
            async for event in agent_service.stream_turn(
                db, current_user, turn, llm
            ):
                yield _sse(event["event"], event["data"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("SSE 流异常")
            yield _sse("error", {"message": "助手暂时不可用，请稍后再试。"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
