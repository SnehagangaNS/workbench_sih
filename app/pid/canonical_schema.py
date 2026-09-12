"""
canonical_schema.py
-------------------
Canonical intermediate representation and data models for P&ID diagrams.
Supports source coordinate preservation, confidence tracking, and extensible metadata.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PIDText:
    id: str
    text: str
    bbox: list[int]  # [x1, y1, x2, y2] in pixels
    confidence: float
    page: int = 1
    category: str = "general"  # tag, spec, note, title, dimension


@dataclass
class PIDSymbol:
    id: str
    type: str  # pump, vessel, tank, gate_valve, control_valve, pressure_transmitter, etc.
    bbox: list[int]  # [x1, y1, x2, y2]
    confidence: float
    page: int = 1
    tag: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class PIDLine:
    id: str
    points: list[list[int]]  # [[x1, y1], [x2, y2], ...]
    line_type: str = "piping"  # piping, instrument_signal, electrical
    spec: str | None = None
    page: int = 1


@dataclass
class PIDConnection:
    from_id: str
    to_id: str
    relationship: str  # connected_to, upstream_of, downstream_of, monitored_by, controlled_by
    confidence: float = 1.0
    line_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PIDPage:
    page: int
    width: int
    height: int
    dpi: int
    symbols: list[PIDSymbol] = field(default_factory=list)
    texts: list[PIDText] = field(default_factory=list)
    lines: list[PIDLine] = field(default_factory=list)
    connections: list[PIDConnection] = field(default_factory=list)


@dataclass
class PIDDocument:
    document_id: str
    filename: str
    created_at: int
    pages: list[PIDPage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
