"""
schema.py
---------
Data models for organizational knowledge grounding.
Retains rich metadata: document name, type, department, author, date, revision/version,
section/page, access scope/permissions, and equipment tags.
"""

from dataclasses import dataclass, field, asdict
import hashlib
import time
from typing import Any, Dict, List, Optional


@dataclass
class KnowledgeDocument:
    document_id: str
    document_name: str
    source_type: str = "General"  # SOP, Manual, Standard, Procedure, WorkInstruction, TechnicalReport, Correspondence, P&ID
    revision: str = "1.0"
    is_current_revision: bool = True
    department: str = "General"
    author: str = "Internal"
    date: str = ""
    access_scope: List[str] = field(default_factory=lambda: ["all"])
    tags: List[str] = field(default_factory=list)
    equipment_tags: List[str] = field(default_factory=list)
    filepath: str = ""
    created_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    revision: str = "1.0"
    is_current_revision: bool = True
    section: str = "General"
    page: int = 1
    source_type: str = "General"
    department: str = "General"
    author: str = "Internal"
    date: str = ""
    access_scope: List[str] = field(default_factory=lambda: ["all"])
    tags: List[str] = field(default_factory=list)
    equipment_tags: List[str] = field(default_factory=list)

    def to_metadata_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source": self.document_name,
            "revision": self.revision,
            "is_current": "true" if self.is_current_revision else "false",
            "section": self.section,
            "page": self.page,
            "source_type": self.source_type,
            "department": self.department,
            "author": self.author,
            "date": self.date,
            "access_scope": ",".join(self.access_scope),
            "tags": ",".join(self.tags),
            "equipment_tags": ",".join(self.equipment_tags),
        }

    @classmethod
    def from_metadata_dict(cls, chunk_id: str, text: str, meta: Dict[str, Any]) -> "KnowledgeChunk":
        return cls(
            chunk_id=chunk_id,
            document_id=str(meta.get("document_id", "")),
            document_name=str(meta.get("source", meta.get("document_name", "Unknown"))),
            text=text,
            revision=str(meta.get("revision", "1.0")),
            is_current_revision=str(meta.get("is_current", "true")).lower() == "true",
            section=str(meta.get("section", "General")),
            page=int(meta.get("page", 1)),
            source_type=str(meta.get("source_type", "General")),
            department=str(meta.get("department", "General")),
            author=str(meta.get("author", "Internal")),
            date=str(meta.get("date", "")),
            access_scope=[s.strip() for s in str(meta.get("access_scope", "all")).split(",") if s.strip()],
            tags=[t.strip() for t in str(meta.get("tags", "")).split(",") if t.strip()],
            equipment_tags=[e.strip() for e in str(meta.get("equipment_tags", "")).split(",") if e.strip()],
        )
