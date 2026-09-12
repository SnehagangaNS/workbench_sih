"""
rendering.py
------------
Multi-format image rendering for P&ID engineering drawings:
Supports PDF (.pdf), Word (.docx/.doc), PowerPoint (.pptx/.ppt), and direct raster images (.png, .jpg, .bmp, etc.).
Preserves page dimensions, coordinate systems, and fine-grained visual details (300-600 DPI).
"""

import io
from pathlib import Path
from PIL import Image, ImageDraw
from app.ingestion.ocr import extract_docx_embedded_images, extract_pptx_embedded_images


def safe_to_rgb(img: Image.Image) -> Image.Image:
    """
    Safely converts any PIL Image to RGB mode.
    If the image has transparency (RGBA, LA, or P with transparency), composites it onto a solid white background
    to prevent transparent pixels from turning black upon direct RGB conversion.
    """
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        img_rgba = img.convert("RGBA")
        background.paste(img_rgba, mask=img_rgba.split()[3])
        return background
    return img.convert("RGB")


def render_document_to_images(
    file_path: str,
    dpi: int = 300,
    output_dir: str | Path | None = None,
) -> list[tuple[str, int, int]]:
    """
    Renders any input file (PDF, DOCX, PPTX, PNG, JPG, BMP, etc.) into one or more high-res page images.
    Returns a list of tuples: [(saved_image_path, width, height), ...]
    """
    path = Path(file_path)
    if path.name.startswith("~$"):
        clean_name = path.name.replace("~$", "")
        clean_p = path.parent / clean_name
        if clean_p.exists():
            path = clean_p
            file_path = str(clean_p)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    out_d = Path(output_dir) if output_dir else path.parent
    out_d.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    stem = path.stem

    rendered = []

    # 1. Direct Raster Image formats
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
        try:
            with Image.open(str(path)) as img:
                img_rgb = safe_to_rgb(img)
                out_img_path = out_d / f"{stem}_page_1.png"
                img_rgb.save(str(out_img_path), "PNG")
                return [(str(out_img_path), img_rgb.width, img_rgb.height)]
        except Exception:
            pass

    # 2. Word Documents (.docx / .doc)
    if suffix in {".docx", ".doc"}:
        embedded_imgs = extract_docx_embedded_images(str(path))
        if embedded_imgs:
            for idx, img_tmp_path in enumerate(embedded_imgs, start=1):
                try:
                    with Image.open(img_tmp_path) as img:
                        img_rgb = safe_to_rgb(img)
                        out_img_path = out_d / f"{stem}_page_{idx}.png"
                        img_rgb.save(str(out_img_path), "PNG")
                        rendered.append((str(out_img_path), img_rgb.width, img_rgb.height))
                except Exception:
                    pass
                finally:
                    try:
                        Path(img_tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            if rendered:
                return rendered

    # 3. PowerPoint Presentations (.pptx / .ppt)
    if suffix in {".pptx", ".ppt"}:
        embedded_imgs = extract_pptx_embedded_images(str(path))
        if embedded_imgs:
            for idx, img_tmp_path in enumerate(embedded_imgs, start=1):
                try:
                    with Image.open(img_tmp_path) as img:
                        img_rgb = safe_to_rgb(img)
                        out_img_path = out_d / f"{stem}_page_{idx}.png"
                        img_rgb.save(str(out_img_path), "PNG")
                        rendered.append((str(out_img_path), img_rgb.width, img_rgb.height))
                except Exception:
                    pass
                finally:
                    try:
                        Path(img_tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            if rendered:
                return rendered

    # 4. PDF Documents (.pdf)
    if suffix == ".pdf":
        page_count = 1
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            page_count = max(len(reader.pages), 1)
        except Exception:
            pass

        for page_num in range(1, page_count + 1):
            res = _render_single_pdf_page(str(path), page_num, dpi, out_d, stem)
            if res:
                rendered.append(res)
        if rendered:
            return rendered

    # 5. Generic Fallback: try opening with PIL
    try:
        with Image.open(str(path)) as img:
            img_rgb = safe_to_rgb(img)
            out_img_path = out_d / f"{stem}_page_1.png"
            img_rgb.save(str(out_img_path), "PNG")
            return [(str(out_img_path), img_rgb.width, img_rgb.height)]
    except Exception:
        pass

    # 6. Default synthetic canvas if file cannot be rasterized directly
    canvas_w = int(11 * dpi)
    canvas_h = int(8.5 * dpi)
    img = Image.new("RGB", (canvas_w, canvas_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((100, 100), f"P&ID Document: {path.name}", fill=(0, 0, 0))
    out_img_path = out_d / f"{stem}_page_1.png"
    img.save(str(out_img_path), "PNG")
    return [(str(out_img_path), canvas_w, canvas_h)]


def _render_single_pdf_page(
    pdf_path: str,
    page_num: int,
    dpi: int,
    output_dir: Path,
    stem: str,
) -> tuple[str, int, int] | None:
    out_img_path = output_dir / f"{stem}_page_{page_num}.png"
    pdf_p = Path(pdf_path)

    # Try pdf2image rasterization
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(
            str(pdf_p),
            dpi=dpi,
            first_page=page_num,
            last_page=page_num,
        )
        if images:
            img = images[0]
            img.save(str(out_img_path), "PNG")
            return str(out_img_path), img.width, img.height
    except Exception:
        pass

    # Fallback to PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(str(pdf_p))
        page = doc.load_page(page_num - 1)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(out_img_path))
        return str(out_img_path), pix.width, pix.height
    except Exception:
        pass

    # Basic PyPDF fallback
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_p))
        if page_num <= len(reader.pages):
            page = reader.pages[page_num - 1]
            for count, image_file_object in enumerate(page.images):
                img = Image.open(io.BytesIO(image_file_object.data))
                img_rgb = safe_to_rgb(img)
                img_rgb.save(str(out_img_path), "PNG")
                return str(out_img_path), img_rgb.width, img_rgb.height
    except Exception:
        pass

    # Fallback synthetic canvas for PDF page
    canvas_w = int(11 * dpi)
    canvas_h = int(8.5 * dpi)
    img = Image.new("RGB", (canvas_w, canvas_h), color=(255, 255, 255))
    img.save(str(out_img_path), "PNG")
    return str(out_img_path), canvas_w, canvas_h


def render_pdf_page_high_res(
    pdf_path: str,
    page_num: int = 1,
    dpi: int = 300,
    output_dir: str | Path | None = None,
) -> tuple[str, int, int]:
    """
    Legacy wrapper for backward compatibility.
    """
    res_list = render_document_to_images(file_path=pdf_path, dpi=dpi, output_dir=output_dir)
    if res_list:
        if 1 <= page_num <= len(res_list):
            return res_list[page_num - 1]
        return res_list[0]
    canvas_w = int(11 * dpi)
    canvas_h = int(8.5 * dpi)
    return "", canvas_w, canvas_h

