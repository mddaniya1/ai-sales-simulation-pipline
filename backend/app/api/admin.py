import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import require_admin
from app.config import get_settings
from app.database import get_db
from app.models import SimulationConfig, User
from app.schemas import SimulationConfigOut, SimulationConfigUpdate
from app.services.rag import extract_text_from_file, ingest_document

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}

PERSONA_PRESETS = [
    "Extreme Price Resistance",
    "Tech-Savvy Luxury Buyer",
    "Skeptical & Defensive Buyer",
]


async def _get_or_create_config(db: AsyncSession) -> SimulationConfig:
    result = await db.execute(select(SimulationConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = SimulationConfig(
            sales_context="Enterprise software renewal meeting with a Fortune 500 procurement lead.",
            hidden_persona="Skeptical & Defensive Buyer",
            chroma_collection="default_products",
        )
        db.add(config)
        await db.flush()
        await db.refresh(config)
    return config


@router.get("/personas")
async def list_personas(_: User = Depends(require_admin)) -> dict:
    return {"personas": PERSONA_PRESETS}


@router.get("/config", response_model=SimulationConfigOut)
async def get_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SimulationConfig:
    return await _get_or_create_config(db)


@router.put("/config", response_model=SimulationConfigOut)
async def update_config(
    body: SimulationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SimulationConfig:
    config = await _get_or_create_config(db)
    config.sales_context = body.sales_context
    config.hidden_persona = body.hidden_persona
    await db.flush()
    await db.refresh(config)
    return config


@router.post("/upload", response_model=SimulationConfigOut)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SimulationConfig:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")

    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    dest = Path(settings.upload_dir) / safe_name
    dest.write_bytes(content)

    try:
        text = extract_text_from_file(dest)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    config = await _get_or_create_config(db)
    collection = f"products_{config.id.hex[:12]}"
    chunk_count = ingest_document(collection, text)
    if chunk_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No text extracted from file")

    config.document_filename = file.filename
    config.chroma_collection = collection
    await db.flush()
    await db.refresh(config)
    return config
