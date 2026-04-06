"""
app/rag/pipeline.py — RAG pipeline with graceful fallback.
If ChromaDB is unavailable, store/retrieve operations are silently skipped.
"""
from __future__ import annotations
import re
from app.utils.logger import log

_embedder = None
_chroma_client = None


def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            log.info("rag.loading_embedder")
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            log.warning("rag.embedder_load_failed", error=str(exc))
    return _embedder


def get_chroma():
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            from app.config import get_settings
            settings = get_settings()
            client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
            # Test connection
            client.heartbeat()
            _chroma_client = client
            log.info("rag.chroma_connected")
        except Exception as exc:
            log.warning("rag.chroma_unavailable", error=str(exc))
            return None
    return _chroma_client


def chunk_text(text: str, max_tokens: int = 200, overlap: int = 40) -> list[str]:
    if not text or not text.strip():
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        words = para.split()
        if len(current.split()) + len(words) <= max_tokens:
            current = (current + " " + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks if chunks else [text[:500]]


def store_context(collection_name: str, doc_id: str, text: str, metadata: dict) -> None:
    """Store embeddings in ChromaDB. Silently skips if ChromaDB unavailable."""
    try:
        chroma = get_chroma()
        if chroma is None:
            log.warning("rag.store_skipped_no_chroma", doc_id=doc_id)
            return

        embedder = get_embedder()
        if embedder is None:
            log.warning("rag.store_skipped_no_embedder", doc_id=doc_id)
            return

        chunks = chunk_text(text)
        if not chunks:
            return

        try:
            collection = chroma.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            # Try creating tenant/database first
            try:
                chroma.create_tenant("default_tenant")
            except Exception:
                pass
            try:
                chroma.create_database("default_database", tenant="default_tenant")
            except Exception:
                pass
            collection = chroma.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        embeddings = embedder.encode(chunks, convert_to_list=True)
        flat_meta = {k: str(v) for k, v in metadata.items()}
        metadatas = [flat_meta | {"chunk_index": str(i)} for i in range(len(chunks))]

        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        log.info("rag.stored", collection=collection_name, doc_id=doc_id, chunks=len(chunks))

    except Exception as exc:
        log.warning("rag.store_failed_continuing", error=str(exc))


def retrieve_context(
    collection_name: str,
    query: str,
    n_results: int = 3,
    where: dict | None = None,
) -> list[str]:
    """Retrieve from ChromaDB. Returns empty list if unavailable."""
    try:
        chroma = get_chroma()
        if chroma is None:
            return []

        embedder = get_embedder()
        if embedder is None:
            return []

        collection = chroma.get_collection(name=collection_name)
        query_embedding = embedder.encode([query], convert_to_list=True)
        kwargs: dict = {"query_embeddings": query_embedding, "n_results": n_results}
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)
        return results.get("documents", [[]])[0]

    except Exception as exc:
        log.warning("rag.retrieve_failed_returning_empty", error=str(exc))
        return []