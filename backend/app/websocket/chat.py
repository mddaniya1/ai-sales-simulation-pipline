import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import decode_token
from app.database import AsyncSessionLocal
from app.models import MessageLog, SenderRole, SessionStatus, SimulationSession, User
from app.services.gemini_chain import SessionMemory, generate_customer_reply
from app.services.rag import retrieve_context
from app.services.session_manager import session_manager

router = APIRouter()


async def _authenticate_ws(token: str | None, db: AsyncSession) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        return result.scalar_one_or_none()
    except Exception:
        return None


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: UUID):
    token = websocket.query_params.get("token")
    await websocket.accept()

    async with AsyncSessionLocal() as db:
        user = await _authenticate_ws(token, db)
        if not user:
            await websocket.send_json({"type": "error", "detail": "Unauthorized"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        result = await db.execute(
            select(SimulationSession)
            .options(selectinload(SimulationSession.config))
            .where(
                SimulationSession.id == session_id,
                SimulationSession.user_id == user.id,
                SimulationSession.status == SessionStatus.active,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await websocket.send_json({"type": "error", "detail": "Session not found or ended"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        memory = await session_manager.get_memory(session_id)
        if not memory:
            memory = SessionMemory(
                sales_context=session.config.sales_context,
                hidden_persona=session.config.hidden_persona,
                chroma_collection=session.config.chroma_collection,
            )
            registered = await session_manager.register(session_id, memory)
            if not registered:
                await websocket.send_json(
                    {"type": "error", "detail": "Maximum concurrent sessions reached. Try again later."}
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        lock = await session_manager.get_lock(session_id)
        if not lock:
            await websocket.send_json({"type": "error", "detail": "Session lock unavailable"})
            await websocket.close()
            return

        await websocket.send_json(
            {
                "type": "session_ready",
                "session_id": str(session_id),
                "active_sessions": session_manager.active_count(),
            }
        )

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                    continue

                msg_type = data.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if msg_type != "message":
                    await websocket.send_json({"type": "error", "detail": "Unknown message type"})
                    continue

                content = (data.get("content") or "").strip()
                if not content:
                    await websocket.send_json({"type": "error", "detail": "Empty message"})
                    continue

                async with lock:
                    now = datetime.now(UTC)
                    user_log = MessageLog(
                        session_id=session_id,
                        sender_role=SenderRole.salesperson,
                        content=content,
                        timestamp=now,
                    )
                    db.add(user_log)
                    await db.flush()

                    context = retrieve_context(memory.chroma_collection, content)
                    reply = await generate_customer_reply(memory, content, context)

                    ai_log = MessageLog(
                        session_id=session_id,
                        sender_role=SenderRole.ai_customer,
                        content=reply,
                        timestamp=datetime.now(UTC),
                    )
                    db.add(ai_log)
                    await db.commit()

                await websocket.send_json(
                    {
                        "type": "message",
                        "role": "ai_customer",
                        "content": reply,
                        "timestamp": ai_log.timestamp.isoformat(),
                    }
                )
        except WebSocketDisconnect:
            pass
        finally:
            await db.commit()
