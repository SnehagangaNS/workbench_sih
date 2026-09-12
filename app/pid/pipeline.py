"""
pipeline.py
-----------
Main orchestration engine for P&ID intelligence:
1. High-DPI PDF Page Rendering
2. Local Bounding-Box OCR Text Extraction
3. SAHI / OpenCV Tiled Symbol Detection
4. OpenCV Piping Line & Connection Detection
5. Spatial Entity Association
6. Canonical Structured P&ID JSON Construction
7. NetworkX Knowledge Graph Generation & Storage
"""

import json
import time
from pathlib import Path
from typing import Dict, Any

from app.pid.canonical_schema import PIDDocument, PIDPage
from app.pid.entity_association import associate_entities
from app.pid.knowledge_graph import PIDKnowledgeGraph
from app.pid.line_detector import detect_lines_opencv
from app.pid.ocr_engine import extract_pid_text
from app.pid.rendering import render_document_to_images
from app.pid.symbol_detector import detect_symbols_sahi_yolo

PID_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "pid"
PID_DATA_DIR.mkdir(parents=True, exist_ok=True)


async def process_pid_document(pdf_path: str, dpi: int = 300) -> Dict[str, Any]:
    """
    Runs full local P&ID analysis pipeline over any engineering drawing file (PDF, DOCX, PPTX, PNG, JPG, BMP, etc.).
    Saves artifacts to data/pid/{pid_id}/ and returns metadata dict.
    """
    pdf_p = Path(pdf_path)
    pid_id = f"pid_{pdf_p.stem}_{int(time.time())}"
    artifact_dir = PID_DATA_DIR / pid_id
    pages_dir = artifact_dir / "pages"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    doc = PIDDocument(
        document_id=pid_id,
        filename=pdf_p.name,
        created_at=int(time.time()),
        pages=[],
    )

    # Multi-format page rendering
    rendered_pages = render_document_to_images(
        file_path=str(pdf_p),
        dpi=dpi,
        output_dir=pages_dir,
    )

    for page_idx, (page_img_path, width, height) in enumerate(rendered_pages, start=1):
        # 1. OCR Bounding-Box Text Extraction
        texts = extract_pid_text(page_img_path, page_num=page_idx)

        # 2. Symbol Detection
        symbols = detect_symbols_sahi_yolo(page_img_path, page_num=page_idx)

        # 3. Line & Piping Detection
        lines = detect_lines_opencv(page_img_path, page_num=page_idx)

        # 4. Entity Association
        symbols, connections = associate_entities(symbols=symbols, texts=texts, lines=lines)

        page_obj = PIDPage(
            page=page_idx,
            width=width,
            height=height,
            dpi=dpi,
            symbols=symbols,
            texts=texts,
            lines=lines,
            connections=connections,
        )
        doc.pages.append(page_obj)

    # 5. Build & Save NetworkX Knowledge Graph
    kg = PIDKnowledgeGraph()
    kg.build_from_document(doc)
    kg.save_graph(artifact_dir / "graph.json")

    # 6. Save Canonical Structured P&ID JSON
    with open(artifact_dir / "detections.json", "w", encoding="utf-8") as f:
        json.dump(doc.to_dict(), f, indent=2)

    # 7. Save Metadata
    first_page_img = ""
    if rendered_pages:
        try:
            first_page_img = str(Path(rendered_pages[0][0]).relative_to(PID_DATA_DIR.parent.parent))
        except Exception:
            first_page_img = str(rendered_pages[0][0])

    metadata = {
        "pid_id": pid_id,
        "filename": pdf_p.name,
        "page_count": len(doc.pages),
        "total_symbols": sum(len(p.symbols) for p in doc.pages),
        "total_texts": sum(len(p.texts) for p in doc.pages),
        "total_lines": sum(len(p.lines) for p in doc.pages),
        "total_connections": sum(len(p.connections) for p in doc.pages),
        "page_image": first_page_img,
        "artifact_dir": str(artifact_dir),
    }

    with open(artifact_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def load_pid_graph(pid_id: str) -> PIDKnowledgeGraph | None:
    artifact_dir = PID_DATA_DIR / pid_id
    graph_path = artifact_dir / "graph.json"
    if not graph_path.exists():
        return None
    kg = PIDKnowledgeGraph()
    kg.load_graph(graph_path)
    return kg


def get_latest_pid_id() -> str | None:
    dirs = sorted(PID_DATA_DIR.glob("pid_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if dirs:
        return dirs[0].name
    return None
