import re


def extract_case_references(text):

    pattern = r'([A-Z][A-Za-z\s]+ v\. [A-Z][A-Za-z\s]+)'

    matches = re.findall(pattern, text)

    return list(set(matches))