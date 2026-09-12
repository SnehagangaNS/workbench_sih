"""
file_tools.py
-------------
read_file / write_file / list_files - sandboxed to the workspace directory.
Every path is resolved and checked to stay inside WORKSPACE_ROOT so the
agent (or a malicious prompt inside an ingested document) cannot read or
write outside the sandbox.
"""

from pathlib import Path

WORKSPACE_ROOT = (Path(__file__).parent.parent.parent / "data").resolve()
WORKSPACE_ROOT.mkdir(exist_ok=True)


class PathEscapeError(Exception):
    pass


def _safe_path(relative_path: str) -> Path:
    rel_str = str(relative_path).strip().strip("'\"")

    # 1. Direct absolute path check
    p = Path(rel_str)
    if p.is_absolute():
        try:
            resolved = p.resolve()
            if WORKSPACE_ROOT in resolved.parents or resolved == WORKSPACE_ROOT:
                if resolved.exists():
                    return resolved
        except Exception:
            pass

    # 2. Normalize slashes & strip redundant leading "data/"
    normalized = rel_str.replace("\\", "/")
    if normalized.startswith("data/"):
        normalized = normalized[5:]

    candidate = (WORKSPACE_ROOT / normalized).resolve()
    if (WORKSPACE_ROOT in candidate.parents or candidate == WORKSPACE_ROOT) and candidate.exists():
        return candidate

    # 3. Handle models replacing spaces in filenames with slashes/backslashes
    subpath = normalized
    for prefix in ["uploads/", "data/uploads/", "data/"]:
        idx = normalized.find(prefix)
        if idx != -1:
            subpath = normalized[idx + len(prefix):]
            break

    unslashed_filename = subpath.replace("/", " ")
    for search_dir in [WORKSPACE_ROOT / "uploads", WORKSPACE_ROOT]:
        test_candidate = (search_dir / unslashed_filename).resolve()
        if test_candidate.exists():
            return test_candidate

    # 4. Basename and fuzzy search over all files in WORKSPACE_ROOT
    all_files = [f for f in WORKSPACE_ROOT.rglob("*") if f.is_file()]
    target_name = unslashed_filename.lower()
    target_base = Path(normalized).name.lower()

    for f in all_files:
        if f.name.lower() in (target_name, target_base):
            return f

    simplified_target = target_name.replace(" ", "").replace("_", "").replace("-", "")
    for f in all_files:
        simplified_f = f.name.lower().replace(" ", "").replace("_", "").replace("-", "")
        if simplified_f == simplified_target:
            return f

    # Fallback to standard path check
    if WORKSPACE_ROOT not in candidate.parents and candidate != WORKSPACE_ROOT:
        raise PathEscapeError(f"Path '{relative_path}' escapes the sandboxed workspace.")
    return candidate


def read_file(relative_path: str, max_chars: int = 4000) -> str:
    path = _safe_path(relative_path)
    if not path.exists():
        return f"ERROR: file not found: {relative_path}"

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from app.ingestion.ocr import extract_pdf_text_direct, is_pdf_text_layer_usable, ocr_scanned_pdf
            from pypdf import PdfReader
            text = extract_pdf_text_direct(str(path))
            reader = PdfReader(str(path))
            if not is_pdf_text_layer_usable(text, num_pages=len(reader.pages)):
                text = ocr_scanned_pdf(str(path))
        except Exception as e:
            text = f"Failed to extract PDF text from {path.name}: {e}"
    elif suffix in {".docx", ".doc"}:
        try:
            from app.ingestion.ocr import extract_docx_text
            text = extract_docx_text(str(path))
        except Exception as e:
            text = f"Failed to extract Word document text from {path.name}: {e}"
    elif suffix in {".pptx", ".ppt"}:
        try:
            from app.ingestion.ocr import extract_pptx_text
            text = extract_pptx_text(str(path))
        except Exception as e:
            text = f"Failed to extract PowerPoint text from {path.name}: {e}"
    elif suffix in {".xlsx", ".xls", ".csv"}:
        try:
            from app.ingestion.ocr import extract_spreadsheet_text
            text = extract_spreadsheet_text(str(path))
        except Exception as e:
            text = f"Failed to extract spreadsheet text from {path.name}: {e}"
    elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
        try:
            from app.ingestion.ocr import ocr_image_file
            ocr_res = ocr_image_file(str(path))
            text = ocr_res if ocr_res else f"[Image file {path.name} loaded. No text found via OCR; consider calling describe_image for visual inspection.]"
        except Exception as e:
            text = f"Failed to OCR image file {path.name}: {e}"
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n...[truncated, {len(text)} chars total]"
    return text


def write_file(relative_path: str, content: str) -> str:
    path = _safe_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {relative_path}"


def list_files(relative_dir: str = "") -> list[str]:
    path = _safe_path(relative_dir)
    if not path.exists():
        return []
    return [str(p.relative_to(WORKSPACE_ROOT)) for p in path.rglob("*") if p.is_file()]


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read text/extracted content of any document or image file in the workspace (PDF, DOCX, PPTX, XLSX, PNG, JPG, etc.).",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file in the workspace (creates or overwrites).",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["relative_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {"relative_dir": {"type": "string"}},
                "required": [],
            },
        },
    },
]
