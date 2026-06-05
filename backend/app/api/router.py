from fastapi import APIRouter

from app.api import admin, auth, export, sessions

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(sessions.router)
api_router.include_router(export.router)
