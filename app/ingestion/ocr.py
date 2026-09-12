"""
ocr.py
------
Multimodal ingestion:
  - Clean printed PDFs -> extract text directly (pypdf), fastest & most
    accurate path, no model needed.
  - Scanned/image-only PDF pages -> rasterize each page, run Tesseract OCR
    (fast, accurate for printed text, tiny footprint - good default).
  - Word documents (.docx/.doc) -> extract text, tables, and embedded drawings/images.
  - PowerPoint decks (.pptx/.ppt) -> extract slide text and embedded images.
  - Spreadsheets (.csv/.xlsx/.xls) -> extract sheet tables using pandas.
  - Images / Handwriting / Engineering drawings / Photos -> Tesseract OCR +
    local vision model with fallback.

Everything runs on-device: pypdf + python-docx + python-pptx + pytesseract +
pdf2image + pandas are all local libraries/binaries, and the vision model call
goes to localhost:11434.
"""

import io
import os
import tempfile
import zipfile
from pathlib import Path

import docx
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from pptx import Presentation
from pypdf import PdfReader

from app.ollama_client import ollama
from app.router import router


def extract_pdf_text_direct(pdf_path: str) -> str:
    """Fast path: PDFs that already have a text layer."""
    reader = PdfReader(pdf_path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def is_pdf_text_layer_usable(text: str, min_chars_per_page: int = 40, num_pages: int = 1) -> bool:
    return len(text.strip()) >= min_chars_per_page * max(num_pages, 1)


def ocr_scanned_pdf(pdf_path: str, dpi: int = 200) -> str:
    """Rasterize each page and OCR with Tesseract - for scanned/image-only PDFs."""
    pages = convert_from_path(pdf_path, dpi=dpi)
    texts = []
    for i, page_img in enumerate(pages):
        text = pytesseract.image_to_string(page_img)
        texts.append(f"--- page {i + 1} ---\n{text}")
    return "\n\n".join(texts)


def extract_docx_embedded_images(docx_path: str) -> list[str]:
    """
    Extracts embedded media images/drawings from a .docx file and saves them
    to temporary file paths. Sanitizes MS Word temporary lock files (~$).
    """
    path = Path(docx_path)
    if path.name.startswith("~$"):
        clean_name = path.name.replace("~$", "")
        clean_p = path.parent / clean_name
        if clean_p.exists():
            docx_path = str(clean_p)
        else:
            return []

    image_paths = []
    try:
        with zipfile.ZipFile(docx_path, "r") as z:
            for filename in z.namelist():
                if filename.startswith("word/media/") and filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")
                ):
                    img_bytes = z.read(filename)
                    suffix = Path(filename).suffix
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tmp.write(img_bytes)
                    tmp.close()
                    image_paths.append(tmp.name)
    except Exception:
        pass
    return image_paths


def extract_pptx_embedded_images(pptx_path: str) -> list[str]:
    """
    Extracts embedded media images/drawings from a .pptx file and saves them
    to temporary file paths.
    """
    image_paths = []
    try:
        with zipfile.ZipFile(pptx_path, "r") as z:
            for filename in z.namelist():
                if filename.startswith("ppt/media/") and filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")
                ):
                    img_bytes = z.read(filename)
                    suffix = Path(filename).suffix
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tmp.write(img_bytes)
                    tmp.close()
                    image_paths.append(tmp.name)
    except Exception:
        pass
    return image_paths


def extract_docx_text(docx_path: str) -> str:
    """Extract text paragraphs, tables, AND embedded drawing OCR from Word (.docx / .doc) files."""
    path = Path(docx_path)
    if path.name.startswith("~$"):
        clean_name = path.name.replace("~$", "")
        clean_p = path.parent / clean_name
        if clean_p.exists():
            docx_path = str(clean_p)
        else:
            return f"[Temporary Word lock file '{path.name}' encountered. Target file '{clean_name}' not found.]"

    try:
        doc = docx.Document(docx_path)
    except Exception as e:
        return f"[Notice: Unable to parse document '{path.name}': {e}]"

    parts = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                parts.append(" | ".join(row_cells))

    # Extract embedded drawings/images inside the docx file
    embedded_images = extract_docx_embedded_images(docx_path)
    if embedded_images:
        parts.append(f"--- Embedded Drawings & Images ({len(embedded_images)} found) ---")
        for idx, img_path in enumerate(embedded_images, start=1):
            try:
                ocr_txt = ocr_image_file(img_path)
                if ocr_txt:
                    parts.append(f"[Embedded Drawing #{idx} OCR Text]:\n{ocr_txt}")
                else:
                    parts.append(f"[Embedded Drawing #{idx}]: (Drawing/image present)")
            except Exception:
                pass
            try:
                os.remove(img_path)
            except Exception:
                pass

    return "\n\n".join(parts)


def extract_pptx_text(pptx_path: str) -> str:
    """Extract text from slides and shape frames in PowerPoint (.pptx / .ppt) files."""
    prs = Presentation(pptx_path)
    slides_text = []
    for i, slide in enumerate(prs.slides):
        slide_parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    t = paragraph.text.strip()
                    if t:
                        slide_parts.append(t)
        if slide_parts:
            slides_text.append(f"--- Slide {i + 1} ---\n" + "\n".join(slide_parts))
    return "\n\n".join(slides_text)


def ocr_image_file(image_path: str) -> str:
    """Extract text from any image file using Tesseract OCR."""
    img = Image.open(image_path)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        img_rgba = img.convert("RGBA")
        background.paste(img_rgba, mask=img_rgba.split()[3])
        img = background
    else:
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img)
    return text.strip()


async def vision_describe_image(image_path: str, mode: str = "photo") -> str:
    """
    Route an image, handwritten document, or document containing drawings (.docx / .pptx)
    to the vision model or OCR engine. Handles embedded drawings inside Word/PowerPoint docs cleanly.
    """
    path = Path(image_path)
    suffix = path.suffix.lower()

    # If a .docx file is passed to describe_image, extract and analyze its embedded drawings!
    if suffix in {".docx", ".doc"}:
        embedded_imgs = extract_docx_embedded_images(image_path)
        if embedded_imgs:
            descriptions = []
            for idx, img_p in enumerate(embedded_imgs, start=1):
                desc = await vision_describe_image(img_p, mode=mode)
                descriptions.append(f"--- Embedded Drawing/Diagram #{idx} ---\n{desc}")
                try:
                    os.remove(img_p)
                except Exception:
                    pass
            docx_txt = extract_docx_text(image_path)
            if docx_txt:
                descriptions.insert(0, f"--- Document Text ---\n{docx_txt}")
            return "\n\n".join(descriptions)
        else:
            return extract_docx_text(image_path)

    if suffix in {".pptx", ".ppt"}:
        embedded_imgs = extract_pptx_embedded_images(image_path)
        if embedded_imgs:
            descriptions = []
            for idx, img_p in enumerate(embedded_imgs, start=1):
                desc = await vision_describe_image(img_p, mode=mode)
                descriptions.append(f"--- Embedded Drawing/Diagram #{idx} ---\n{desc}")
                try:
                    os.remove(img_p)
                except Exception:
                    pass
            pptx_txt = extract_pptx_text(image_path)
            if pptx_txt:
                descriptions.insert(0, f"--- Presentation Text ---\n{pptx_txt}")
            return "\n\n".join(descriptions)
        else:
            return extract_pptx_text(image_path)

    # Standard image file (PNG, JPG, BMP, etc.)
    prompts = {
        "handwriting": (
            "Transcribe all handwritten and printed text in this image exactly "
            "as written. Preserve line breaks. If a word is illegible, mark it "
            "as [illegible] rather than guessing."
        ),
        "engineering_drawing": (
            "Describe this engineering drawing: identify labeled components, "
            "dimensions/measurements shown, any title block information "
            "(drawing number, title, revision), and notable annotations. "
            "List dimensions exactly as shown."
        ),
        "photo": (
            "Describe what is shown in this image in detail, including any "
            "visible text, labels, or numbers."
        ),
    }
    prompt = prompts.get(mode, prompts["photo"])
    try:
        vision_model = router.vision_model()
        v_text = await ollama.vision_chat(vision_model.name, prompt, image_path)
        if v_text and len(v_text.strip()) > 10:
            return v_text
    except Exception:
        pass

    # Fallback to Tesseract OCR
    try:
        ocr_text = ocr_image_file(image_path)
        if ocr_text:
            return f"[Tesseract OCR Extracted Text]\n{ocr_text}"
    except Exception as e:
        return f"[Image processing notice: OCR fallback error: {e}]"

    return "[Image processed: No text could be extracted or vision model was unavailable.]"


def extract_spreadsheet_text(file_path: str) -> str:
    """
    Converts a CSV/XLSX into a readable text representation for RAG indexing.
    """
    path = Path(file_path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        return f"--- {path.name} ---\n{df.to_string(index=False)}"

    sheets = pd.read_excel(path, sheet_name=None)
    parts = []
    for sheet_name, df in sheets.items():
        parts.append(f"--- {path.name} :: sheet '{sheet_name}' ---\n{df.to_string(index=False)}")
    return "\n\n".join(parts)


async def ingest_document(file_path: str, mode: str | None = None) -> dict:
    """
    Unified ingestion entry point. Auto-detects handling based on file type
    unless `mode` is explicitly given.

    Returns {"text": ..., "method": ..., "source": filename}
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        direct_text = extract_pdf_text_direct(file_path)
        reader = PdfReader(file_path)
        if is_pdf_text_layer_usable(direct_text, num_pages=len(reader.pages)):
            return {"text": direct_text, "method": "pdf_text_layer", "source": path.name}
        ocr_text = ocr_scanned_pdf(file_path)
        return {"text": ocr_text, "method": "tesseract_ocr", "source": path.name}

    if suffix in {".docx", ".doc"}:
        text = extract_docx_text(file_path)
        return {"text": text, "method": "docx_extract", "source": path.name}

    if suffix in {".pptx", ".ppt"}:
        text = extract_pptx_text(file_path)
        return {"text": text, "method": "pptx_extract", "source": path.name}

    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
        vision_mode = mode or "photo"
        text = await vision_describe_image(file_path, mode=vision_mode)
        try:
            ocr_text = ocr_image_file(file_path)
            if ocr_text and ocr_text not in text:
                text += f"\n\n--- Tesseract OCR Transcript ---\n{ocr_text}"
        except Exception:
            pass
        return {"text": text, "method": f"multimodal_ocr:{vision_mode}", "source": path.name}

    if suffix in {".csv", ".xlsx", ".xls"}:
        text = extract_spreadsheet_text(file_path)
        return {"text": text, "method": "spreadsheet_extract", "source": path.name}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"text": text, "method": "raw_text", "source": path.name}
    except Exception as e:
        raise ValueError(f"Unsupported file type '{suffix}': {e}")
