"""
connector.py
------------
LocalKnowledgeConnector interface & implementation:
Provides a consistent, fully local abstraction for ingesting, querying, and managing
organizational knowledge (SOPs, manuals, work instructions, engineering standards,
past correspondence, technical reports).
Operates 100% on-premise without external network calls.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ingestion.ocr import ingest_document
from app.knowledge.correspondence import parse_email_file, parse_json_correspondence
from app.knowledge.retriever import retriever_instance
from app.knowledge.schema import KnowledgeDocument, KnowledgeChunk
from app.rag import vector_store
from app.rag.chunker import chunk_text

KNOWLEDGE_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "knowledge"
KNOWLEDGE_DATA_DIR.mkdir(parents=True, exist_ok=True)


class LocalKnowledgeConnector:
    """
    Unified local organizational knowledge connector.
    Supports local file system, folder mounts, document repositories, and email exports.
    """

    def __init__(self):
        self.doc_index_path = KNOWLEDGE_DATA_DIR / "documents.json"
        self._load_document_index()

    def _load_document_index(self):
        self.documents: Dict[str, Dict[str, Any]] = {}
        if self.doc_index_path.exists():
            try:
                with open(self.doc_index_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception:
                self.documents = {}

    def _save_document_index(self):
        with open(self.doc_index_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, indent=2)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        user_scopes: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves relevant organizational knowledge chunks using local hybrid retrieval.
        Applies permission scope filtering BEFORE context creation.
        """
        return await retriever_instance.retrieve(
            query_text=query,
            top_k=top_k,
            user_scopes=user_scopes,
            source_type=source_type,
            department=department,
        )

    def retrieve(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered document by document_id."""
        return self.documents.get(document_id)

    def get_source_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Gets full metadata for a document."""
        doc = self.documents.get(document_id)
        if doc:
            return doc.get("metadata", {})
        return None

    def retrieve_by_metadata(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filters registered documents by metadata attributes."""
        matched = []
        for doc_id, doc in self.documents.items():
            meta = doc.get("metadata", {})
            match = True
            for k, v in filters.items():
                if str(meta.get(k, "")).lower() != str(v).lower():
                    match = False
                    break
            if match:
                matched.append(doc)
        return matched

    def get_related_documents(self, document_id: str) -> List[Dict[str, Any]]:
        """Finds related documents sharing the same department, tags, or equipment."""
        target = self.documents.get(document_id)
        if not target:
            return []
        meta = target.get("metadata", {})
        dept = meta.get("department")
        source_type = meta.get("source_type")

        related = []
        for d_id, doc in self.documents.items():
            if d_id == document_id:
                continue
            d_meta = doc.get("metadata", {})
            if d_meta.get("department") == dept or d_meta.get("source_type") == source_type:
                related.append(doc)
        return related[:5]

    async def ingest_organizational_document(
        self,
        file_path: str,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ingests an organizational document (SOP, Manual, Engineering Standard, Report, PDF, DOCX, XLSX).
        Extracts content, enriches metadata, chunks text, and stores vectors in local ChromaDB.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 1. Parse Document Text
        parsed = await ingest_document(str(path))
        text = parsed.get("text", "")
        if not text.strip():
            raise ValueError(f"No text extracted from {path.name}")

        # 2. Build Metadata
        meta_in = custom_metadata or {}
        doc_id = meta_in.get("document_id") or f"doc_{path.stem}_{int(path.stat().st_mtime)}"
        doc_name = meta_in.get("document_name") or meta_in.get("title") or path.name
        revision = meta_in.get("revision") or "1.0"
        is_current = meta_in.get("is_current_revision", True)
        source_type = meta_in.get("source_type") or "General"
        department = meta_in.get("department") or "Engineering"
        author = meta_in.get("author") or "Internal"
        date_str = meta_in.get("date") or ""
        scopes = meta_in.get("access_scope") or ["all"]
        tags = meta_in.get("tags") or []
        equipment = meta_in.get("equipment_tags") or []

        doc_obj = KnowledgeDocument(
            document_id=doc_id,
            document_name=doc_name,
            source_type=source_type,
            revision=revision,
            is_current_revision=is_current,
            department=department,
            author=author,
            date=date_str,
            access_scope=scopes,
            tags=tags,
            equipment_tags=equipment,
            filepath=str(path),
        )

        # 3. Chunk and Enrich Metadata
        chunks_text, _, chunk_ids = chunk_text(text, source_name=doc_name)
        chunks_metadata = []

        for idx, c_text in enumerate(chunks_text, start=1):
            chunk = KnowledgeChunk(
                chunk_id=chunk_ids[idx - 1],
                document_id=doc_id,
                document_name=doc_name,
                text=c_text,
                revision=revision,
                is_current_revision=is_current,
                section=f"Section {idx}",
                page=idx,
                source_type=source_type,
                department=department,
                author=author,
                date=date_str,
                access_scope=scopes,
                tags=tags,
                equipment_tags=equipment,
            )
            chunks_metadata.append(chunk.to_metadata_dict())

        # 4. Save to ChromaDB
        if chunks_text:
            await vector_store.add_chunks(
                chunks=chunks_text,
                metadatas=chunks_metadata,
                ids=chunk_ids,
            )

        # 5. Register in document index
        doc_entry = {
            "document_id": doc_id,
            "filename": path.name,
            "filepath": str(path),
            "chunks_count": len(chunks_text),
            "metadata": doc_obj.to_dict(),
        }
        self.documents[doc_id] = doc_entry
        self._save_document_index()

        return doc_entry

    async def ingest_correspondence_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Ingests past correspondence (email exports .eml, .json, meeting notes, project messages).
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        parsed_items = []
        if suffix == ".eml":
            parsed_items.append(parse_email_file(str(path)))
        elif suffix == ".json":
            parsed_items.extend(parse_json_correspondence(str(path)))
        else:
            txt = path.read_text(encoding="utf-8", errors="replace")
            meta = {
                "document_name": f"Correspondence: {path.name}",
                "source_type": "Correspondence",
                "department": "Communications",
                "revision": "1.0",
                "is_current_revision": True,
                "access_scope": ["all"],
            }
            parsed_items.append((txt, meta))

        results = []
        for full_text, meta in parsed_items:
            doc_id = meta.get("thread_id") or f"corr_{path.stem}_{len(results)+1}"
            doc_name = meta.get("document_name") or path.name

            chunks_text, _, chunk_ids = chunk_text(full_text, source_name=doc_name)
            chunks_metadata = []

            for idx, c_text in enumerate(chunks_text, start=1):
                chunk = KnowledgeChunk(
                    chunk_id=chunk_ids[idx - 1],
                    document_id=doc_id,
                    document_name=doc_name,
                    text=c_text,
                    revision="1.0",
                    is_current_revision=True,
                    section=f"Message Part {idx}",
                    page=idx,
                    source_type="Correspondence",
                    department=meta.get("department", "Communications"),
                    author=meta.get("author", "Internal"),
                    date=meta.get("date", ""),
                    access_scope=meta.get("access_scope") or ["all"],
                    tags=meta.get("tags") or ["correspondence"],
                    equipment_tags=meta.get("equipment_tags") or [],
                )
                chunks_metadata.append(chunk.to_metadata_dict())

            if chunks_text:
                await vector_store.add_chunks(
                    chunks=chunks_text,
                    metadatas=chunks_metadata,
                    ids=chunk_ids,
                )

            doc_entry = {
                "document_id": doc_id,
                "filename": path.name,
                "filepath": str(path),
                "chunks_count": len(chunks_text),
                "metadata": meta,
            }
            self.documents[doc_id] = doc_entry
            results.append(doc_entry)

        self._save_document_index()
        return results


# Global singleton instance
local_knowledge_connector = LocalKnowledgeConnector()
