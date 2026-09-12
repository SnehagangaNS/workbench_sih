"""
ocr_engine.py
--------------
Local OCR Engine for P&ID drawings.
Extracts engineering text, equipment/instrument tags, line specifications, and notes
along with exact pixel bounding box coordinates [x1, y1, x2, y2] and confidence scores.
"""

import re
from pathlib import Path
import pytesseract
from PIL import Image

from app.pid.canonical_schema import PIDText


# Regular expressions for common P&ID engineering tag conventions
TAG_PATTERNS = {
    "equipment": r"\b([A-Z]{1,3}-\d{3,4}[A-Z]?)\b",  # e.g., P-101, V-102A, TK-201
    "instrument": r"\b([A-Z]{2,4}-\d{3,4}[A-Z]?)\b", # e.g., PT-101, FT-202, LCV-301
    "line": r"\b(\d{1,2}\"-[A-Z0-9]+-\d+)\b",         # e.g., 6"-ABC-1234
}


def categorize_text(text: str) -> str:
    t = text.strip()
    if re.search(TAG_PATTERNS["instrument"], t):
        return "instrument_tag"
    if re.search(TAG_PATTERNS["equipment"], t):
        return "equipment_tag"
    if re.search(TAG_PATTERNS["line"], t):
        return "line_spec"
    return "general"


def extract_pid_text(
    image_path: str,
    page_num: int = 1,
    min_confidence: float = 0.3,
) -> list[PIDText]:
    """
    Runs local OCR over high-resolution page image and returns a list of PIDText objects
    containing recognized text, confidence score, bounding box [x1, y1, x2, y2], and page number.
    """
    img_path = Path(image_path)
    if not img_path.exists():
        return []

    img = Image.open(str(img_path))
    ocr_texts: list[PIDText] = []

    # Use Tesseract image_to_data for word-level bounding boxes and confidence scores
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        n_boxes = len(data["text"])
        
        current_line_words = []
        current_bbox = None
        current_conf = []

        for i in range(n_boxes):
            word = data["text"][i].strip()
            conf = float(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.0

            if not word or conf < min_confidence:
                continue

            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            x1, y1, x2, y2 = x, y, x + w, y + h

            cat = categorize_text(word)
            item_id = f"text_{page_num}_{len(ocr_texts) + 1:04d}"

            ocr_texts.append(
                PIDText(
                    id=item_id,
                    text=word,
                    bbox=[x1, y1, x2, y2],
                    confidence=round(conf, 3),
                    page=page_num,
                    category=cat,
                )
            )
    except Exception:
        pass

    return ocr_texts
