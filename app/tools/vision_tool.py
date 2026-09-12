"""
vision_tool.py
--------------
Exposes the local vision model to the agent loop directly, so a task like
"look at uploads/note.jpg and transcribe it, then put it in a report" can
be done in one multi-step task - not just through the separate /api/ingest
upload button. Ingestion (with RAG indexing) and this tool call the same
underlying vision_describe_image function in app/ingestion/ocr.py.
"""

from app.ingestion.ocr import vision_describe_image
from app.tools.file_tools import _safe_path


async def describe_image(relative_path: str, mode: str = "photo") -> str:
    path = _safe_path(relative_path)
    if not path.exists():
        return f"ERROR: file not found: {relative_path}"
    return await vision_describe_image(str(path), mode=mode)


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "describe_image",
            "description": (
                "Use the local vision model to read/describe an image file in the "
                "workspace - handwriting, engineering drawings, scanned photos, or "
                "general images. Use mode='handwriting' to transcribe handwritten "
                "text, mode='engineering_drawing' for technical drawings with "
                "dimensions/labels, or mode='photo' for general image description."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["handwriting", "engineering_drawing", "photo"],
                    },
                },
                "required": ["relative_path"],
            },
        },
    }
]
