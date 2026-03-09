import re
from typing import List, Dict


def clean_text(text: str) -> str:

    patterns = [
        r'Indian Kanoon.*',
        r'http[s]?://.*',
        r'Page \d+',
        r'Downloaded.*'
    ]

    for p in patterns:
        text = re.sub(p, '', text, flags=re.IGNORECASE)

    text = re.sub(r'\r', '\n', text)
    text = re.sub(r'\n{2,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)

    return text.strip()


def clean_pages(pages: List[Dict]) -> List[Dict]:

    cleaned = []

    for page in pages:
        cleaned.append({
            "page_number": page["page_number"],
            "text": clean_text(page["text"])
        })

    return cleaned