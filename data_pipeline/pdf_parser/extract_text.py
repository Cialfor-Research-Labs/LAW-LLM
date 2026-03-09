import fitz
from typing import List, Dict


def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extracts text from a PDF and returns structured page data.
    """

    pages = []

    try:
        doc = fitz.open(pdf_path)

        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            text = page.get_text("text")

            pages.append({
                "page_number": page_number + 1,
                "text": text
            })

        doc.close()

    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")

    return pages