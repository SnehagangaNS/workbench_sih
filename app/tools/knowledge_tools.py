"""
knowledge_tools.py
------------------
Agent tools for searching and retrieving local organizational knowledge, SOPs,
engineering standards, manuals, work instructions, and past correspondence.
"""

from typing import Any, Dict, List
from app.knowledge.connector import local_knowledge_connector

TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Searches internal organizational knowledge base (SOPs, manuals, work instructions, engineering standards, procedures, past correspondence, technical reports). Ground answers in retrieved source sections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or engineering question (e.g. 'valve isolation procedure', 'SOP for P-101 startup', 'past correspondence about V-101 exception').",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Optional filter by document type: 'SOP', 'Manual', 'Standard', 'Procedure', 'WorkInstruction', 'Correspondence', 'TechnicalReport', or 'all'.",
                        "default": "all",
                    },
                    "department": {
                        "type": "string",
                        "description": "Optional filter by department: 'Engineering', 'Operations', 'Safety', 'Communications', or 'all'.",
                        "default": "all",
                    },
                    "access_scope": {
                        "type": "string",
                        "description": "User access scope/role for permission filtering: 'all', 'engineering', 'operations', 'admin'.",
                        "default": "all",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_metadata",
            "description": "Gets full document metadata, revision information, author, department, and access permissions for a document ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "Document ID (e.g. 'SOP-104', 'doc_manual_123').",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
]


async def search_knowledge_base(
    query: str,
    source_type: str = "all",
    department: str = "all",
    access_scope: str = "all",
) -> Dict[str, Any]:
    """
    Agent tool to query local organizational knowledge.
    """
    scopes = [s.strip() for s in access_scope.split(",") if s.strip()]
    results = await local_knowledge_connector.search(
        query=query,
        top_k=5,
        user_scopes=scopes,
        source_type=source_type,
        department=department,
    )

    if not results:
        return {
            "query": query,
            "count": 0,
            "results": [],
            "message": "No organizational documentation found matching query in local knowledge base.",
        }

    formatted = []
    for r in results:
        chunk = r.get("chunk")
        formatted.append({
            "citation": r.get("citation"),
            "document_name": r.get("document_name"),
            "revision": r.get("revision"),
            "is_current": r.get("is_current"),
            "section": r.get("section"),
            "page": r.get("page"),
            "source_type": r.get("source_type"),
            "text_snippet": r.get("text"),
            "relevance_score": r.get("score"),
        })

    return {
        "query": query,
        "count": len(formatted),
        "results": formatted,
    }


def get_document_metadata(document_id: str) -> Dict[str, Any]:
    """
    Gets document metadata by ID.
    """
    meta = local_knowledge_connector.get_source_metadata(document_id)
    if not meta:
        return {"error": f"Document ID '{document_id}' not found in knowledge connector index."}
    return {"document_id": document_id, "metadata": meta}
