import os
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_DIR = "../data_pipeline/parsed_json"
OUTPUT_FILE = "../chunk_output/judgement_chunks.jsonl"

# Adjust depending on CPU / disk speed
MAX_THREADS = 8


def create_chunk(case_metadata, section_type, text):
    return {
        "id": str(uuid.uuid4()),
        "case_name": case_metadata.get("case_name"),
        "court": case_metadata.get("court"),
        "date": case_metadata.get("date"),
        "judges": case_metadata.get("judges"),
        "section_type": section_type,
        "text": text
    }


def process_json_file(filepath):
    chunks = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata = {
            "case_name": data.get("case_name"),
            "court": data.get("court"),
            "date": data.get("date"),
            "judges": data.get("judges")
        }

        fields_to_chunk = [
            "facts",
            "issues",
            "arguments_petitioner",
            "arguments_respondent",
            "ratio_decidendi",
            "judgment",
            "obiter_dicta"
        ]

        for field in fields_to_chunk:
            text = data.get(field)

            if text and len(text.strip()) > 20:
                chunks.append(create_chunk(metadata, field, text))

    except Exception as e:
        print(f"Failed to process {filepath}: {e}")

    return chunks


def main():

    json_files = [
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.endswith(".json")
    ]

    all_chunks = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = {executor.submit(process_json_file, f): f for f in json_files}

        for future in as_completed(futures):
            chunks = future.result()
            if chunks:
                all_chunks.extend(chunks)

    # Write chunks
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk) + "\n")

    print(f"\nTotal chunks created: {len(all_chunks)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()