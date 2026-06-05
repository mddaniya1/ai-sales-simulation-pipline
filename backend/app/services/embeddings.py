import google.generativeai as genai

from app.config import get_settings

settings = get_settings()


def configure_genai() -> None:
    if settings.google_api_key:
        genai.configure(api_key=settings.google_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed documents using Google embedding-001."""
    configure_genai()
    vectors: list[list[float]] = []
    for text in texts:
        result = genai.embed_content(
            model=settings.embedding_model,
            content=text,
            task_type="retrieval_document",
        )
        vectors.append(result["embedding"])
    return vectors


def embed_query(query: str) -> list[float]:
    configure_genai()
    result = genai.embed_content(
        model=settings.embedding_model,
        content=query,
        task_type="retrieval_query",
    )
    return result["embedding"]
