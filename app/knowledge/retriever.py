"""
retriever.py
------------
Local hybrid retrieval engine for organizational knowledge grounding:
- Vector similarity search via ChromaDB
- Keyword & Equipment Tag matching (P-101, V-101, line numbers)
- Document revision weighting (prefers current approved revision; surfaces version conflicts)
- Access scope / Permission filtering BEFORE sending context to the local LLM
"""

import re
from typing import Any, Dict, List, Optional
from app.knowledge.schema import KnowledgeChunk
from app.rag import vector_store


class HybridKnowledgeRetriever:
    def __init__(self):
        pass

    async def retrieve(
        self,
        query_text: str,
        top_k: int = 5,
        user_scopes: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid retrieval over local ChromaDB organizational knowledge.
        Applies permission scope filtering BEFORE returning context.
        """
        active_user_scopes = set([s.lower() for s in (user_scopes or ["all"])])

        # Extract potential equipment tags (e.g. P-101, V-101, TK-102, PT-101)
        equipment_matches = set(re.findall(r"\b[A-Z]{1,4}-\d{2,4}[A-Z]?\b", query_text))

        # Query vector store
        raw_hits = await vector_store.query(text=query_text, n_results=top_k * 3)

        results = []
        seen_chunks = set()

        for hit in raw_hits:
            chunk_id = hit["id"]
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            meta = hit.get("metadata", {})
            text = hit.get("text", "")

            # 1. PERMISSION SCOPE FILTERING
            chunk_scopes_raw = str(meta.get("access_scope", "all")).split(",")
            chunk_scopes = set([s.strip().lower() for s in chunk_scopes_raw if s.strip()])
            
            # If user does not have 'admin' and no matching scope, skip chunk!
            if "admin" not in active_user_scopes and "all" not in chunk_scopes:
                if not (active_user_scopes & chunk_scopes):
                    continue  # Filter out unauthorized content BEFORE LLM context creation

            # 2. SOURCE TYPE & DEPARTMENT FILTERING
            if source_type and source_type.lower() != "all":
                hit_st = str(meta.get("source_type", "")).lower()
                if hit_st and source_type.lower() not in hit_st:
                    continue

            if department and department.lower() != "all":
                hit_dept = str(meta.get("department", "")).lower()
                if hit_dept and department.lower() not in hit_dept:
                    continue

            # 3. RELEVANCE & REVISION SCORE WEIGHTING
            score = float(hit.get("relevance", 0.5))

            # Revision preference: current approved revision gets boost (+0.15)
            is_current = str(meta.get("is_current", "true")).lower() == "true"
            if is_current:
                score += 0.15
            else:
                score -= 0.10  # Deprioritize older superseded revisions

            # Equipment tag match boost (+0.25)
            eq_str = str(meta.get("equipment_tags", "")) + " " + text
            for eq in equipment_matches:
                if eq.lower() in eq_str.lower():
                    score += 0.25

            parsed_chunk = KnowledgeChunk.from_metadata_dict(chunk_id, text, meta)

            results.append({
                "chunk": parsed_chunk,
                "score": round(score, 4),
                "relevance": hit.get("relevance", 0.5),
                "is_current": is_current,
                "document_name": parsed_chunk.document_name,
                "revision": parsed_chunk.revision,
                "section": parsed_chunk.section,
                "page": parsed_chunk.page,
                "source_type": parsed_chunk.source_type,
                "text": text,
                "citation": f"{parsed_chunk.document_name} ({parsed_chunk.revision}) - Section {parsed_chunk.section}, Page {parsed_chunk.page}",
            })

        # Sort by weighted score
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]


retriever_instance = HybridKnowledgeRetriever()
