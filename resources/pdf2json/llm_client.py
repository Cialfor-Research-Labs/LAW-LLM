import json
import time
import logging
import os
from typing import List, Dict, Any
import openai
from tqdm import tqdm
from config import (
    LLM_PROVIDER,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    MAX_RETRIES,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------
# Prompt template (few‑shot)
# ---------------------------------------------------------
SYSTEM_PROMPT = """You are an assistant that converts the raw text of an Indian court judgment
into a strict JSON object that follows the schema below.  The output must be a **single**
JSON object (no markdown, no extra text).  If any field cannot be found, put an empty
string, an empty list, or an empty object as appropriate.

{
  "case_id": "",
  "title": "",
  "court": "",
  "date": "",
  "citation": "",
  "jurisdiction": "India",
  "url": "",
  "source": "Indian Kanoon",
  "area_of_law": "",
  "keywords": [],
  "facts": "",
  "procedural_history": "",
  "legal_issues": [],
  "court_reasoning": "",
  "final_order": "",
  "statutes_cited": [],
  "precedents_cited": [],
  "case_summary": "",
  "chunks": [
    {
      "chunk_id": "",
      "section": "",
      "text": ""
    }
  ]
}

Use the information in the supplied judgment text to fill the fields.
If an item is mentioned more than once, pick the most complete version.
Do NOT hallucinate URLs – use the URL that appears in the text (if any); otherwise leave blank.
"""
# ---------------------------------------------------------

def _call_openai(messages: List[Dict[str, str]]) -> str:
    """Single request to OpenAI ChatCompletion with exponential back‑off."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                temperature=OPENAI_TEMPERATURE,
                messages=messages,
                max_tokens=2500,                # plenty for a 10‑k word judgment
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            wait = 2 ** attempt
            log.warning("OpenAI request failed (attempt %s/%s): %s – retrying in %s s",
                        attempt, MAX_RETRIES, exc, wait)
            time.sleep(wait)
    raise RuntimeError("OpenAI request failed after max retries")

def build_prompt(raw_text: str) -> List[Dict[str, str]]:
    """Construct the message list for the LLM."""
    # Truncate to the first ~12 k tokens if the document is huge.
    # Approx 4 characters per token → 48 k chars ≈ 500 pages, safe for us.
    trimmed = raw_text[:48_000]          # simple char‑cut, fast
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": trimmed},
    ]

def parse_response(response: str) -> Dict[str, Any]:
    """Validate that the LLM actually returned JSON."""
    try:
        # Some LLMs still wrap the JSON in stray back‑ticks – strip them.
        cleaned = response.strip().lstrip("`").rstrip("`")
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.error("JSON decode error: %s – response was: %s", exc, response[:200])
        raise

def convert_judgment_to_json(raw_text: str) -> Dict[str, Any]:
    messages = build_prompt(raw_text)
    raw_response = _call_openai(messages)
    return parse_response(raw_response)
