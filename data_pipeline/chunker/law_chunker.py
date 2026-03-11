import os
import re
import json
import uuid
import pymupdf as fitz
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_DIR = "./pdf_input"
OUTPUT_FILE = "./json_output/law_chunks.jsonl"

MAX_THREADS = 8
CHUNK_SIZE_WORDS = 350


def extract_text_from_pdf(filepath):
    """Extract text from PDF"""
    text = ""

    try:
        doc = fitz.open(filepath)

        for page in doc:
            text += page.get_text()

    except Exception as e:
        print(f"[ERROR] {filepath} → {e}")

    return text


def clean_text(text):
    """Clean extracted text"""

    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'Page\s+\d+', '', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)

    return text.strip()


def chunk_text(text, chunk_size=CHUNK_SIZE_WORDS):
    """Split text into word chunks"""

    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def process_pdf(filepath):
    """Full pipeline for a single PDF"""

    filename = os.path.basename(filepath)

    raw_text = extract_text_from_pdf(filepath)
    cleaned_text = clean_text(raw_text)

    text_chunks = chunk_text(cleaned_text)

    chunk_objects = []

    for chunk in text_chunks:
        chunk_objects.append({
            "id": str(uuid.uuid4()),
            "source_file": filename,
            "text": chunk
        })

    print(f"[DONE] {filename} → {len(chunk_objects)} chunks")

    return chunk_objects


def main():

    pdf_files = [
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.endswith(".pdf")
    ]

    print(f"\nTotal PDFs found: {len(pdf_files)}")
    print(f"Using {MAX_THREADS} threads\n")

    all_chunks = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = [executor.submit(process_pdf, pdf) for pdf in pdf_files]

        for future in as_completed(futures):

            try:
                chunks = future.result()
                all_chunks.extend(chunks)

            except Exception as e:
                print(f"[THREAD ERROR] {e}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        for chunk in all_chunks:
            f.write(json.dumps(chunk) + "\n")

    print("\n--------------------------------")
    print(f"Total chunks created: {len(all_chunks)}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("--------------------------------\n")


if __name__ == "__main__":
    main()