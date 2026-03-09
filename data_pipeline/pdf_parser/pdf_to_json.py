import os
import json

from extract_text import extract_text_from_pdf
from clean_text import clean_pages
from metadata_extractor import extract_metadata
from section_parser import split_into_paragraphs, classify_sections
from citation_extractor import extract_citations
from statuate_extractor import extract_statutes
from entity_extractor import extract_case_references
import traceback

def flatten_and_clean(items):
    """
    Flattens nested lists and keeps only strings.
    Also removes duplicates safely.
    """

    flat = []

    def _flatten(x):
        if isinstance(x, list):
            for i in x:
                _flatten(i)
        elif isinstance(x, str):
            flat.append(x)

    _flatten(items)

    # safe deduplication
    seen = set()
    result = []

    for item in flat:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


def build_json_structure(pdf_path, pages):

    full_text = "\n".join([p["text"] for p in pages])

    metadata = extract_metadata(full_text)

    paragraphs = split_into_paragraphs(full_text)

    sections = classify_sections(paragraphs)

    # Safe extraction
    citations = flatten_and_clean(extract_citations(full_text))
    statutes = flatten_and_clean(extract_statutes(full_text))
    case_references = flatten_and_clean(extract_case_references(full_text))

    data = {
        "metadata": metadata,
        "sections": sections,
        "citations": citations,
        "statutes": statutes,
        "case_references": case_references,
        "full_text": full_text
    }

    return data


def convert_pdf(pdf_path, output_dir):

    print(f"Processing: {pdf_path}")

    pages = extract_text_from_pdf(pdf_path)

    pages = clean_pages(pages)

    data = build_json_structure(pdf_path, pages)

    filename = os.path.basename(pdf_path).replace(".pdf", ".json")

    output_path = os.path.join(output_dir, filename)

    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Saved JSON: {output_path}")


def batch_convert(input_dir, output_dir):

    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input folder not found: {input_dir}")

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("No PDF files found.")
        return

    for pdf in pdf_files:

        pdf_path = os.path.join(input_dir, pdf)

        try:
            convert_pdf(pdf_path, output_dir)

        
        except Exception as e:
            print(f"\nFailed to process {pdf}")
            traceback.print_exc()

if __name__ == "__main__":

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    INPUT_DIR = os.path.join(BASE_DIR, "../input_pdfs")
    OUTPUT_DIR = os.path.join(BASE_DIR, "../output_json")

    batch_convert(INPUT_DIR, OUTPUT_DIR)