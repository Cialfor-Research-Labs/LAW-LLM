import re
from typing import Dict


def extract_metadata(text: str) -> Dict:

    metadata = {}

    lines = text.split("\n")

    # Case title
    if len(lines) > 0:
        metadata["case_title"] = lines[0].strip()

    # Date extraction
    date_match = re.search(r'on (.*?\d{4})', text)
    if date_match:
        metadata["date"] = date_match.group(1)

    # Judge extraction
    judge_match = re.search(r'([A-Z][A-Za-z.\s]+),\s*J\.', text)
    if judge_match:
        metadata["judge"] = judge_match.group(1)

    metadata["source"] = "Indian Kanoon"

    return metadata