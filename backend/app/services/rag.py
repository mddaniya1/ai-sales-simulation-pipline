import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import get_settings
from app.services.embeddings import embed_texts

settings = get_settings()

_chroma_client = None
_USE_CHROMA = False

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    _USE_CHROMA = True
except ImportError:
    chromadb = None  # type: ignore
    ChromaSettings = None  # type: ignore


@dataclass
class _MemoryChunk:
    chunk_id: str
    document: str
    embedding: list[float]


@dataclass
class _MemoryCollection:
    chunks: list[_MemoryChunk] = field(default_factory=list)


_memory_store: dict[str, _MemoryCollection] = {}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_chroma_client():
    global _chroma_client
    if not _USE_CHROMA:
        raise RuntimeError("ChromaDB not installed")
    if _chroma_client is None:
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def _sanitize_collection_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:63]


def _memory_key(collection_name: str) -> str:
    return _sanitize_collection_name(collection_name)


def get_collection(collection_name: str):
    if _USE_CHROMA:
        client = get_chroma_client()
        safe_name = _sanitize_collection_name(collection_name)
        return client.get_or_create_collection(name=safe_name, metadata={"hnsw:space": "cosine"})
    key = _memory_key(collection_name)
    if key not in _memory_store:
        _memory_store[key] = _MemoryCollection()
    return _memory_store[key]


def extract_text_from_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {suffix}")


def ingest_document(collection_name: str, text: str) -> int:
    """Split, embed, and store document chunks. Returns chunk count."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    chunks = splitter.split_text(text)
    if not chunks:
        return 0

    embeddings = embed_texts(chunks)

    if _USE_CHROMA:
        collection = get_collection(collection_name)
        try:
            existing = collection.get()
            if existing and existing.get("ids"):
                collection.delete(ids=existing["ids"])
        except Exception:
            pass
        ids = [str(uuid.uuid4()) for _ in chunks]
        collection.add(ids=ids, documents=chunks, embeddings=embeddings)
        return len(chunks)

    key = _memory_key(collection_name)
    _memory_store[key] = _MemoryCollection(
        chunks=[
            _MemoryChunk(chunk_id=str(uuid.uuid4()), document=doc, embedding=emb)
            for doc, emb in zip(chunks, embeddings)
        ]
    )
    return len(chunks)


def retrieve_context(collection_name: str, query: str, top_k: int | None = None) -> str:
    from app.services.embeddings import embed_query

    k = top_k or settings.rag_top_k

    if _USE_CHROMA:
        collection = get_collection(collection_name)
        count = collection.count()
        if count == 0:
            return "No product documentation has been uploaded yet."
        query_embedding = embed_query(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=min(k, count))
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "No relevant product information found."
        return "\n\n---\n\n".join(docs)

    store = get_collection(collection_name)
    if not store.chunks:
        return "No product documentation has been uploaded yet."

    query_embedding = embed_query(query)
    ranked = sorted(
        store.chunks,
        key=lambda c: _cosine_similarity(query_embedding, c.embedding),
        reverse=True,
    )[:k]
    return "\n\n---\n\n".join(c.document for c in ranked)


def rag_backend() -> str:
    return "chromadb" if _USE_CHROMA else "in-memory"
