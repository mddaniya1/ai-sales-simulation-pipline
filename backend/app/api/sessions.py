from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import get_current_user
from app.database import get_db
from app.models import MessageLog, SenderRole, SessionStatus, SimulationConfig, SimulationSession, User
from app.schemas import MessageCreate, MessageOut, SessionOut
from app.services.gemini_chain import SessionMemory
from app.services.gemini_chain import generate_customer_reply
from app.services.rag import retrieve_context
from app.services.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_active_config(db: AsyncSession) -> SimulationConfig:
    result = await db.execute(select(SimulationConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Simulation not configured. Admin must set up scenario first.",
        )
    return config


@router.post("", response_model=SessionOut)
async def create_session(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SimulationSession:
    config = await _get_active_config(db)
    session = SimulationSession(user_id=user.id, config_id=config.id, status=SessionStatus.active)
    db.add(session)
    await db.flush()
    await db.refresh(session)

    memory = SessionMemory(
        sales_context=config.sales_context,
        hidden_persona=config.hidden_persona,
        chroma_collection=config.chroma_collection,
    )
    await session_manager.register(session.id, memory)
    return session


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SimulationSession:
    result = await db.execute(
        select(SimulationSession).where(
            SimulationSession.id == session_id,
            SimulationSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageLog]:
    result = await db.execute(
        select(SimulationSession).where(
            SimulationSession.id == session_id,
            SimulationSession.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msgs = await db.execute(
        select(MessageLog)
        .where(MessageLog.session_id == session_id)
        .order_by(MessageLog.timestamp)
    )
    return list(msgs.scalars().all())


@router.post("/{session_id}/messages", response_model=MessageOut)
async def send_message_rest(
    session_id: UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageLog:
    """REST fallback for chat (WebSocket preferred)."""
    result = await db.execute(
        select(SimulationSession)
        .options(selectinload(SimulationSession.config))
        .where(SimulationSession.id == session_id, SimulationSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session or session.status != SessionStatus.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active session not found")

    memory = await session_manager.get_memory(session_id)
    if not memory:
        memory = SessionMemory(
            sales_context=session.config.sales_context,
            hidden_persona=session.config.hidden_persona,
            chroma_collection=session.config.chroma_collection,
        )
        await session_manager.register(session_id, memory)

    lock = await session_manager.get_lock(session_id)
    if not lock:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session unavailable")

    async with lock:
        user_log = MessageLog(
            session_id=session_id,
            sender_role=SenderRole.salesperson,
            content=body.content,
        )
        db.add(user_log)
        await db.flush()

        context = retrieve_context(memory.chroma_collection, body.content)
        reply = await generate_customer_reply(memory, body.content, context)

        ai_log = MessageLog(
            session_id=session_id,
            sender_role=SenderRole.ai_customer,
            content=reply,
        )
        db.add(ai_log)
        await db.flush()
        await db.refresh(ai_log)
        return ai_log


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SimulationSession:
    result = await db.execute(
        select(SimulationSession).where(
            SimulationSession.id == session_id,
            SimulationSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.status = SessionStatus.ended
    session.ended_at = datetime.now(UTC)
    await session_manager.unregister(session_id)
    await db.flush()
    await db.refresh(session)
    return session
