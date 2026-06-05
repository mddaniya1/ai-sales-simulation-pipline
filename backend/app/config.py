from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://simuser:simpass@localhost:5432/sales_sim"
    google_api_key: str = ""
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    backend_cors_origins: str = "http://localhost:3000"
    chroma_persist_dir: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    max_concurrent_sessions: int = 20
    max_upload_mb: int = 10
    gemini_model: str = "gemini-1.5-flash"
    embedding_model: str = "models/embedding-001"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
