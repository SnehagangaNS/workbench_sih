"""
vector_store.py
----------------
ChromaDB persistent vector store, fully local (no network calls - Chroma's
default embedding function would try to download from HF, so we ALWAYS
pass our own pre-computed embeddings via app.ollama_client to keep this
air-gapped).
"""

from pathlib import Path

import chromadb

from app.ollama_client import ollama
from app.router import router

DB_PATH = Path(__file__).parent.parent.parent / "data" / "vectorstore"
DB_PATH.mkdir(parents=True, exist_ok=True)

_client = chromadb.PersistentClient(path=str(DB_PATH))
_collection = _client.get_or_create_collection(
    name="org_documents",
    metadata={"hnsw:space": "cosine"},
)


async def add_chunks(chunks: list[str], metadatas: list[dict], ids: list[str]):
    if not chunks:
        return
    embed_model = router.embedding_model()
    try:
        embeddings = await ollama.embed_batch(embed_model.name, chunks)
        _collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
    except Exception as e:
        print(f"[VectorStore Warning] Could not add chunks to vector store: {e}")


async def query(text: str, n_results: int = 5, where: dict | None = None) -> list[dict]:
    embed_model = router.embedding_model()
    query_embedding = await ollama.embed(embed_model.name, text)
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
    )
    hits = []
    if results["documents"]:
        for doc, meta, dist, doc_id in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            results["ids"][0],
        ):
            hits.append({
                "id": doc_id,
                "text": doc,
                "metadata": meta,
                "relevance": round(1 - dist, 4),
            })
    return hits


def collection_stats() -> dict:
    return {"total_chunks": _collection.count()}
