"""
document_search.py
-------------------
Agent-facing tool wrapping the RAG vector store. Returns text chunks WITH
their source filename so the agent (and the final answer) can cite where
each fact came from, instead of presenting retrieved text as its own
unsourced claim.
"""

from app.rag.vector_store import query as vector_query


async def search_documents(query_text: str, top_k: int = 5) -> list[dict]:
    hits = await vector_query(query_text, n_results=top_k)

    # Auto-ingest fallback if vector DB returns no hits
    if not hits:
        try:
            from app.ingestion.ocr import ingest_document
            from app.rag.chunker import chunk_text
            from app.rag.vector_store import add_chunks
            from app.tools.file_tools import _safe_path

            matched_file = _safe_path(query_text)
            if matched_file.exists():
                res = await ingest_document(str(matched_file))
                chunks, metadatas, ids = chunk_text(res["text"], source_name=res["source"])
                if chunks:
                    await add_chunks(chunks, metadatas, ids)
                hits = await vector_query(query_text, n_results=top_k)
                if not hits and chunks:
                    return [
                        {
                            "source": res["source"],
                            "chunk_index": i,
                            "relevance": 1.0,
                            "text": chunk,
                        }
                        for i, chunk in enumerate(chunks[:top_k])
                    ]
        except Exception:
            pass

    return [
        {
            "source": h["metadata"].get("source", "unknown"),
            "chunk_index": h["metadata"].get("chunk_index"),
            "relevance": h["relevance"],
            "text": h["text"],
        }
        for h in hits
    ]


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the organisation's ingested manuals/documents for relevant "
                "passages. Always use this before answering questions about org "
                "policy, procedures, or manual content - do not rely on general "
                "knowledge for those. Returns passages with their source document."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["query_text"],
            },
        },
    }
]
