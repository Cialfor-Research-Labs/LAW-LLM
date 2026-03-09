import re


STATUTE_PATTERNS = [
    r'Consumer Protection Act',
    r'Indian Penal Code',
    r'Code of Civil Procedure',
    r'Section\s+\d+\s+of\s+the\s+[A-Za-z ]+Act'
]


def extract_statutes(text):

    statutes = []

    for pattern in STATUTE_PATTERNS:

        matches = re.findall(pattern, text, re.IGNORECASE)

        statutes.extend(matches)  # ✅ not append

    return list(set(statutes))