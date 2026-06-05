import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.database import Base, engine
from app.models import SimulationConfig
from app.websocket.chat import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default config if empty
    from sqlalchemy import select
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SimulationConfig).limit(1))
        if not result.scalar_one_or_none():
            db.add(
                SimulationConfig(
                    sales_context=(
                        "Enterprise SaaS renewal with a Fortune 500 procurement committee. "
                        "The customer is evaluating whether to renew or switch vendors."
                    ),
                    hidden_persona="Skeptical & Defensive Buyer",
                    chroma_collection="default_products",
                )
            )
            await db.commit()

    yield
    await engine.dispose()


app = FastAPI(
    title="AI Customer Simulation Platform",
    description="Sales training simulator with Gemini RAG and WebSocket chat",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    from app.services.rag import rag_backend
    from app.services.session_manager import session_manager

    return {
        "status": "ok",
        "rag_backend": rag_backend(),
        "active_ws_sessions": session_manager.active_count(),
        "max_concurrent_sessions": settings.max_concurrent_sessions,
    }
