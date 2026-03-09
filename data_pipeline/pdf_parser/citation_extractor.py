import re


CITATION_PATTERNS = [
    r'\(\d{4}\)\s*\d+\s*SCC\s*\d+',
    r'AIR\s*\d{4}\s*SC\s*\d+',
    r'I\(\d{4}\)\s*CPJ\d+'
]


def extract_citations(text):

    citations = []

    for pattern in CITATION_PATTERNS:

        matches = re.findall(pattern, text)

        citations.extend(matches)  # ✅ important

    return list(set(citations))