from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent.runtime import LLMClient, get_llm, run_agent
from app.common.exceptions import BusinessException
from app.models.agent import AgentConversation, AgentMessage
from app.models.boarding import BoardingDraft
from app.models.user import User
from app.schemas.agent import (
    AgentMessageResponse,
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    ToolEvent,
)
from app.services import boarding_service

MAX_HISTORY_MESSAGES = 30


def _get_conversation(db: Session, user: User, conversation_id: int) -> AgentConversation:
    conversation = (
        db.query(AgentConversation)
        .filter(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == user.id,
        )
        .first()
    )
    if not conversation:
        raise BusinessException(message="会话不存在", code=404)
    return conversation


def _create_conversation(db: Session, user: User, title: str) -> AgentConversation:
    conversation = AgentConversation(
        user_id=user.id,
        title=title[:30] or "新对话",
        last_message_at=datetime.now(),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _load_history(db: Session, conversation_id: int) -> list[dict]:
    rows = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == conversation_id)
        .order_by(AgentMessage.id.asc())
        .all()
    )
    rows = rows[-MAX_HISTORY_MESSAGES:]
    while rows and rows[0].role != "user":
        rows = rows[1:]

    history: list[dict] = []
    for row in rows:
        if row.role == "assistant" and row.tool_calls:
            history.append(
                {
                    "role": "assistant",
                    "content": row.content or None,
                    "tool_calls": row.tool_calls,
                }
            )
        elif row.role == "tool":
            if row.tool_call_id:
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": row.tool_call_id,
                        "content": row.content,
                    }
                )
        else:
            history.append({"role": row.role, "content": row.content})
    return history


async def chat(
    db: Session,
    user: User,
    data: ChatRequest,
    llm: LLMClient | None = None,
) -> ChatResponse:
    if not data.messages:
        raise BusinessException(message="消息不能为空")
    last = data.messages[-1]
    if last.role != "user":
        raise BusinessException(message="最后一条消息必须来自用户")

    trace_id = uuid4().hex
    if data.conversation_id is not None:
        conversation = _get_conversation(db, user, data.conversation_id)
        # 已有会话以数据库历史为准，只追加本轮最后一条用户消息，避免客户端重复提交历史。
        db.add(
            AgentMessage(
                conversation_id=conversation.id,
                role="user",
                content=last.content,
                trace_id=trace_id,
            )
        )
    else:
        conversation = _create_conversation(db, user, last.content)
        # 第一次请求允许客户端带上一段上下文，一并落库。
        for item in data.messages:
            db.add(
                AgentMessage(
                    conversation_id=conversation.id,
                    role=item.role,
                    content=item.content,
                    trace_id=trace_id,
                )
            )

    conversation.last_message_at = datetime.now()
    db.commit()

    history = _load_history(db, conversation.id)
    client = llm or get_llm()
    result = await run_agent(
        db=db,
        user=user,
        conversation_id=conversation.id,
        history=history,
        llm=client,
        trace_id=trace_id,
    )

    conversation.last_message_at = datetime.now()
    db.commit()

    draft_payload = None
    if result.draft_id is not None:
        draft = db.get(BoardingDraft, result.draft_id)
        if draft and draft.owner_id == user.id:
            draft_payload = boarding_service.draft_payload(db, draft)

    return ChatResponse(
        conversation_id=conversation.id,
        trace_id=trace_id,
        content=result.content,
        draft=draft_payload,
        tool_events=[ToolEvent(**event) for event in result.tool_events],
    )


def list_conversations(db: Session, user: User) -> list[AgentConversation]:
    return (
        db.query(AgentConversation)
        .filter(AgentConversation.user_id == user.id)
        .order_by(AgentConversation.last_message_at.desc())
        .limit(50)
        .all()
    )


def get_messages(
    db: Session, user: User, conversation_id: int
) -> list[AgentMessage]:
    conversation = _get_conversation(db, user, conversation_id)
    return (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == conversation.id)
        .order_by(AgentMessage.id.asc())
        .all()
    )


def conversation_payload(conversation: AgentConversation) -> dict:
    return ConversationResponse.model_validate(conversation).model_dump()


def message_payload(message: AgentMessage) -> dict:
    return AgentMessageResponse.model_validate(message).model_dump()
