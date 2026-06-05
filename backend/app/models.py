import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    student = "student"


class SessionStatus(str, enum.Enum):
    active = "active"
    ended = "ended"


class SenderRole(str, enum.Enum):
    salesperson = "salesperson"
    ai_customer = "ai_customer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.student, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list["SimulationSession"]] = relationship(back_populates="user")


class SimulationConfig(Base):
    __tablename__ = "simulation_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sales_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hidden_persona: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    document_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chroma_collection: Mapped[str] = mapped_column(String(128), default="default_products", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["SimulationSession"]] = relationship(back_populates="config")


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_configs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.active)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="sessions")
    config: Mapped["SimulationConfig"] = relationship(back_populates="sessions")
    messages: Mapped[list["MessageLog"]] = relationship(
        back_populates="session", order_by="MessageLog.timestamp"
    )


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sender_role: Mapped[SenderRole] = mapped_column(Enum(SenderRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped["SimulationSession"] = relationship(back_populates="messages")
