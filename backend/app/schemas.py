from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models import SenderRole, SessionStatus, UserRole


# Auth
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.student


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    role: UserRole


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}


# Config
class SimulationConfigUpdate(BaseModel):
    sales_context: str = ""
    hidden_persona: str = ""


class SimulationConfigOut(BaseModel):
    id: UUID
    sales_context: str
    hidden_persona: str
    document_filename: str | None
    chroma_collection: str
    updated_at: datetime

    model_config = {"from_attributes": True}


# Sessions
class SessionCreate(BaseModel):
    pass


class SessionOut(BaseModel):
    id: UUID
    config_id: UUID
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: UUID
    session_id: UUID
    timestamp: datetime
    sender_role: SenderRole
    content: str

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


# Export
class ExportLogEntry(BaseModel):
    session_id: UUID
    timestamp: datetime
    sender_role: SenderRole
    content: str
    user_email: str | None = None
