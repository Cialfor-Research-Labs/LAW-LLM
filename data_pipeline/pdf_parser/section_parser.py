import re
from typing import Dict

def split_into_paragraphs(text: str):

    paragraphs = re.split(r'\n\s*\d+\.\s', text)

    return [p.strip() for p in paragraphs if p.strip()]
import re

SECTION_PATTERNS = {

    "facts": [
        r"facts in brief",
        r"facts of the case",
        r"brief facts"
    ],

    "arguments": [
        r"heard counsel",
        r"arguments",
        r"contentions"
    ],

    "reasoning": [
        r"in the light of",
        r"it is clear that",
        r"we are of the opinion"
    ],

    "order": [
        r"we order",
        r"petition dismissed",
        r"appeal allowed",
        r"revision petition is dismissed"
    ]
}


def classify_sections(paragraphs):

    sections = {
        "facts": [],
        "arguments": [],
        "reasoning": [],
        "order": [],
        "other": []
    }

    current_section = "other"

    for para in paragraphs:

        lower = para.lower()

        matched = False

        for section, patterns in SECTION_PATTERNS.items():

            for pattern in patterns:

                if re.search(pattern, lower):

                    current_section = section
                    matched = True
                    break

            if matched:
                break

        sections[current_section].append(para)

    return sections