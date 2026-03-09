import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from pathlib import Path
import logging

log = logging.getLogger(__name__)

def _extract_via_pdfplumber(pdf_path: Path) -> str:
    """Return plain‑text if PDF has an internal text layer."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages).strip()
        if len(text) > 200:                 # heuristic: enough readable text
            return text
    except Exception as exc:
        log.debug("pdfplumber failed on %s: %s", pdf_path, exc)
    return ""

def _extract_via_ocr(pdf_path: Path) -> str:
    """Fallback OCR – rasterises each page and runs Tesseract."""
    images = convert_from_path(str(pdf_path), fmt="png", dpi=300)
    txt_pages = []
    for i, img in enumerate(images, start=1):
        txt = pytesseract.image_to_string(img, lang="eng")
        txt_pages.append(f"[Page {i}]\n{txt}")
    return "\n".join(txt_pages).strip()

def extract_text(pdf_path: Path) -> str:
    """
    Try digital extraction first; if the result is tiny, fall back to OCR.
    Returns a single string containing the whole document.
    """
    text = _extract_via_pdfplumber(pdf_path)
    if len(text) < 300:                     # very short → probably scanned
        text = _extract_via_ocr(pdf_path)
    return text
