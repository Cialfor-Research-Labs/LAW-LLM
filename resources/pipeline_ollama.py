import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request

try:
    from tqdm import tqdm  # type: ignore
except Exception:  # pragma: no cover
    def tqdm(iterable, **kwargs):  # type: ignore
        return iterable

MODEL = "llama3.1:8b"
DEFAULT_INPUT_DIR = Path("judgements")
DEFAULT_OUTPUT_DIR = Path("JSON_judgements")

SCHEMA_TEMPLATE: Dict[str, Any] = {
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
    "chunks": [],
}

ALLOWED_CHUNK_SECTIONS = {
    "facts",
    "procedural_history",
    "legal_issues",
    "court_reasoning",
    "final_order",
    "other",
}

GENERIC_ISSUE_PHRASES = {
    "technical mistake",
    "corporate governance",
    "efficient work of the system",
    "efficiency of system",
}


def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text from all pages.
    Preferred: PyMuPDF (fitz)
    Fallbacks: pdfplumber, then pypdf
    """
    text_parts: List[str] = []

    try:
        import fitz  # type: ignore

        with fitz.open(pdf_path) as doc:
            for page in doc:
                text_parts.append(page.get_text("text"))
        return "\n".join(text_parts)
    except Exception:
        pass

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(pdf_path)) as doc:
            for page in doc.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception:
        pass

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception:
        pass

    pdftotext_bin = shutil.which("pdftotext")
    if pdftotext_bin:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_out:
            tmp_path = Path(tmp_out.name)
        try:
            subprocess.run(
                [pdftotext_bin, str(pdf_path), str(tmp_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            return tmp_path.read_text(encoding="utf-8", errors="ignore")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    # Repo-local fallback: bundled venv PyMuPDF CLI.
    local_pymupdf = Path(__file__).resolve().parent / "path" / "to" / "venv" / "bin" / "pymupdf"
    if local_pymupdf.exists():
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_out:
            tmp_path = Path(tmp_out.name)
        try:
            subprocess.run(
                [
                    str(local_pymupdf),
                    "gettext",
                    "-mode",
                    "simple",
                    "-noformfeed",
                    "-output",
                    str(tmp_path),
                    str(pdf_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return tmp_path.read_text(encoding="utf-8", errors="ignore")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    raise RuntimeError(
        "Failed to extract PDF text. Install one of: pymupdf, pdfplumber, pypdf, or poppler-utils (pdftotext)."
    )


def clean_text(text: str) -> str:
    """Remove common scraper/header noise while preserving legal content."""
    if not text:
        return ""

    lines = text.replace("\r", "\n").split("\n")
    cleaned_lines: List[str] = []

    skip_patterns = [
        r"^\s*Page\s+\d+\s+of\s+\d+\s*$",
        r"^\s*Downloaded on\s*[:-].*$",
        r"^\s*Print Page\s*.*$",
        r"^\s*Author\s*:\s*.*$",
        r"^\s*Bench\s*:\s*.*$",
        r"^\s*Indian Kanoon\s*-?.*$",
        r"^\s*http[s]?://.*$",
    ]

    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            cleaned_lines.append("")
            continue

        if any(re.match(pattern, line, flags=re.IGNORECASE) for pattern in skip_patterns):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_llm_excerpt(text: str, max_chars: int = 90000) -> str:
    """Preserve beginning and end of long judgments to keep metadata + final order."""
    if len(text) <= max_chars:
        return text

    head = int(max_chars * 0.6)
    tail = max_chars - head
    return f"{text[:head]}\n\n[... content truncated for context window ...]\n\n{text[-tail:]}"


def build_prompt(cleaned_text: str, case_id: str, source_url: str) -> str:
    schema_preview = json.dumps(
        {
            **SCHEMA_TEMPLATE,
            "case_id": case_id,
            "url": source_url,
            "chunks": [{"chunk_id": f"{case_id}_1", "section": "", "text": ""}],
        },
        ensure_ascii=False,
        indent=2,
    )

    excerpt = build_llm_excerpt(cleaned_text)

    return f"""
You are extracting training-quality structured legal data from an Indian judgment.

Rules:
1. Return ONLY valid JSON (no markdown, no comments).
2. Do not hallucinate. If missing, keep empty string "" or empty array [].
3. Keep extracted text faithful to judgment language.
4. date must be YYYY-MM-DD when clear; otherwise "".
5. keywords/statutes_cited/precedents_cited/legal_issues must be arrays of short strings.
6. Fill jurisdiction="India", source="Indian Kanoon", case_id="{case_id}", url="{source_url}".
7. Do not include keys outside the schema.
8. chunks must contain meaningful, non-overlapping sections from judgment text.
   Use section names from this set where possible:
   ["facts", "procedural_history", "legal_issues", "court_reasoning", "final_order", "other"]
9. legal_issues must be the court's actual legal questions (e.g., "Whether ...").
   Do NOT output generic themes like "corporate governance", "efficient system", or "technical mistake".
10. procedural_history must be chronological and include lower-forum result and appellate outcome when present.
11. court_reasoning must reflect the court's adopted reasoning, not merely parties' arguments.
12. final_order must reflect the operative final appellate direction (including any modification to interest/compensation).

Schema:
{schema_preview}

Judgment text:
{excerpt}
""".strip()


def call_ollama(prompt: str, model: str = MODEL) -> str:
    """Run local Ollama model via API, fallback to CLI."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.1},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=600) as resp:
            response_payload = json.loads(resp.read().decode("utf-8"))
        message = response_payload.get("message", {})
        content = message.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
    except error.URLError:
        pass

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        raise RuntimeError(
            "Unable to connect to Ollama API and `ollama` CLI not found in PATH."
        )

    # Ask CLI for strict JSON output via instruction in prompt.
    cli_prompt = (
        f"{prompt}\n\nReturn strictly valid JSON only. Do not include markdown fences."
    )
    proc = subprocess.run(
        [ollama_bin, "run", model],
        input=cli_prompt,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Ollama CLI failed: {proc.stderr.strip()}")
    if not proc.stdout.strip():
        raise RuntimeError("Ollama returned an empty response.")
    return proc.stdout


def extract_json_payload(raw_output: str) -> Dict[str, Any]:
    """Parse JSON robustly, including fenced/block outputs if any."""
    text = raw_output.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("Model output did not contain valid JSON")


def to_list_of_strings(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_text_field(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def normalize_court_name(court: str, cleaned_text: str) -> str:
    if court:
        c = re.sub(r"\s+", " ", court).strip()
        if "CONSUMER DISPUTES REDRESSAL COMMISSION" in c.upper() and "STATE" not in c.upper():
            m = re.search(
                r"([A-Za-z ]+State Consumer Disputes Redressal Commission)",
                cleaned_text,
                flags=re.IGNORECASE,
            )
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip()
        return c

    m = re.search(
        r"([A-Za-z ]+(?:High Court|Supreme Court|State Consumer Disputes Redressal Commission|District Consumer Disputes Redressal Forum))",
        cleaned_text,
        flags=re.IGNORECASE,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def infer_area_of_law(cleaned_text: str, parsed_area: str) -> str:
    if parsed_area:
        return parsed_area
    t = cleaned_text.lower()
    if "consumer protection" in t or "deficiency in service" in t or "consumer dispute" in t:
        if "college" in t or "university" in t or "education" in t:
            return "Consumer Protection / Education Services"
        if "telecom" in t or "bsnl" in t or "mobile" in t:
            return "Consumer Protection / Telecom Services"
        return "Consumer Protection"
    if "criminal" in t or "ipc" in t:
        return "Criminal Law"
    if "writ petition" in t or "article 226" in t:
        return "Constitutional Law"
    return ""


def extract_legal_issues_from_text(cleaned_text: str, limit: int = 6) -> List[str]:
    issues: List[str] = []
    patterns = [
        r"(Whether[^.?!]{20,250}[.?!])",
        r"(The\s+question\s+for\s+(?:determination|consideration)\s+[^.?!]{10,250}[.?!])",
        r"(The\s+issue\s+[^.?!]{10,250}[.?!])",
        r"(Point\s+for\s+determination\s+[^.?!]{10,250}[.?!])",
    ]
    for pat in patterns:
        for m in re.finditer(pat, cleaned_text, flags=re.IGNORECASE):
            s = re.sub(r"\s+", " ", m.group(1)).strip()
            if len(s) >= 25:
                issues.append(s.rstrip(".?!"))
    deduped: List[str] = []
    seen = set()
    for i in issues:
        k = i.lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(i)
        if len(deduped) >= limit:
            break
    return deduped


def refine_legal_issues(issues: List[str], cleaned_text: str) -> List[str]:
    refined: List[str] = []
    for issue in issues:
        s = re.sub(r"\s+", " ", issue).strip(" -;:")
        low = s.lower()
        if not s:
            continue
        if low in GENERIC_ISSUE_PHRASES:
            continue
        if len(s.split()) < 4:
            continue
        refined.append(s)

    if not refined:
        refined = extract_legal_issues_from_text(cleaned_text)

    if not refined:
        # Last fallback from explicit legal anchors.
        t = cleaned_text.lower()
        if "deficiency in service" in t:
            refined.append("Whether the opposite party committed deficiency in service")
        if "entitled to refund" in t or "refund" in t:
            refined.append("Whether the complainant is entitled to refund and interest")
        if "maintainable" in t:
            refined.append("Whether the complaint is maintainable under the applicable law")

    return refined[:6]


def build_procedural_history(cleaned_text: str, parsed_history: str) -> str:
    if parsed_history and len(parsed_history.split()) >= 18:
        return " ".join(parsed_history.split()[:140]).strip()

    candidates: List[str] = []
    lines = [ln.strip() for ln in cleaned_text.split("\n") if ln.strip()]
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in ["complaint", "district forum", "state commission", "appeal", "impugned order", "allowed", "dismissed", "modified", "set aside"]):
            if len(ln.split()) >= 5:
                candidates.append(ln)

    # Prefer chronological narrative from selected lines.
    selected: List[str] = []
    for c in candidates:
        cc = re.sub(r"\s+", " ", c).strip()
        if cc not in selected:
            selected.append(cc)
        if len(selected) >= 6:
            break

    if not selected:
        return parsed_history

    history = " ".join(selected)
    history = re.sub(r"\s+", " ", history).strip()
    return " ".join(history.split()[:140]).strip()


def refine_court_reasoning(reasoning: str, cleaned_text: str, chunks: List[Dict[str, str]]) -> str:
    bad_markers = [
        "appellant contended",
        "appellant argued",
        "respondent contended",
        "respondent argued",
        "learned counsel submitted",
    ]
    text = reasoning.strip()
    if text:
        sentences = _sentences(text)
        kept = [s for s in sentences if not any(b in s.lower() for b in bad_markers)]
        text = " ".join(kept).strip()

    if text and len(text.split()) >= 18:
        return text

    reasoning_chunks = [c["text"] for c in chunks if c.get("section") == "court_reasoning"]
    if reasoning_chunks:
        return re.sub(r"\s+", " ", " ".join(reasoning_chunks[:2])).strip()

    # Fallback from keyword scan in source text.
    candidates = []
    for s in _sentences(cleaned_text):
        low = s.lower()
        if any(k in low for k in ["we find", "held that", "therefore", "hence", "in our view", "it is clear that"]):
            candidates.append(s)
    return " ".join(candidates[:4]).strip()


def extract_final_order_from_text(cleaned_text: str) -> str:
    tail = cleaned_text[-30000:]
    sentences = _sentences(tail)
    selected: List[str] = []
    for s in sentences:
        low = s.lower()
        if any(
            k in low
            for k in [
                "appeal is allowed",
                "appeal is dismissed",
                "complaint is allowed",
                "complaint is dismissed",
                "impugned order is modified",
                "order is modified",
                "set aside",
                "directed to pay",
                "interest",
                "compensation",
                "cost",
                "disposed of",
            ]
        ):
            selected.append(s)
    if not selected:
        return ""
    return re.sub(r"\s+", " ", " ".join(selected[-4:])).strip()


def refine_final_order(parsed_final: str, cleaned_text: str) -> str:
    fallback = extract_final_order_from_text(cleaned_text)
    if not parsed_final:
        return fallback

    parsed = re.sub(r"\s+", " ", parsed_final).strip()
    if not fallback:
        return parsed

    # If interest rates differ and text indicates modification, trust textual final order.
    parsed_rates = re.findall(r"(\d{1,2})\s*%", parsed)
    fallback_rates = re.findall(r"(\d{1,2})\s*%", fallback)
    if parsed_rates and fallback_rates and parsed_rates[-1] != fallback_rates[-1]:
        if re.search(r"\b(modified|impugned order|appeal)\b", fallback, flags=re.IGNORECASE):
            return " ".join(fallback.split()[:120]).strip()

    if len(parsed.split()) < 8:
        return " ".join(fallback.split()[:120]).strip()
    return " ".join(parsed.split()[:120]).strip()


def split_chunks_from_text(case_id: str, cleaned_text: str, chunk_chars: int = 2500) -> List[Dict[str, str]]:
    """Fallback chunking if model does not return usable chunks."""
    paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
    chunks: List[Dict[str, str]] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= chunk_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = para

    if current:
        chunks.append(current)

    out: List[Dict[str, str]] = []
    for idx, txt in enumerate(chunks, start=1):
        section = "other"
        low = txt.lower()
        if any(k in low for k in ["facts", "brief facts"]):
            section = "facts"
        elif any(k in low for k in ["issue", "question for determination", "points for consideration"]):
            section = "legal_issues"
        elif any(k in low for k in ["held", "reason", "analysis", "we find", "court is of the view"]):
            section = "court_reasoning"
        elif any(k in low for k in ["appeal is", "petition is", "ordered", "disposed of", "final order"]):
            section = "final_order"

        out.append({"chunk_id": f"{case_id}_{idx}", "section": section, "text": txt})

    return out


def normalize_chunks(case_id: str, chunks_value: Any, cleaned_text: str) -> List[Dict[str, str]]:
    if not isinstance(chunks_value, list):
        return split_chunks_from_text(case_id, cleaned_text)

    normalized: List[Dict[str, str]] = []
    for idx, item in enumerate(chunks_value, start=1):
        if not isinstance(item, dict):
            continue

        text = normalize_text_field(item.get("text"))
        if not text:
            continue

        section = normalize_text_field(item.get("section")).lower() or "other"
        if section not in ALLOWED_CHUNK_SECTIONS:
            section = "other"
        chunk_id = normalize_text_field(item.get("chunk_id")) or f"{case_id}_{idx}"

        normalized.append({"chunk_id": chunk_id, "section": section, "text": text})

    if not normalized:
        return split_chunks_from_text(case_id, cleaned_text)

    return normalized


def enforce_schema(case_id: str, source_url: str, cleaned_text: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(SCHEMA_TEMPLATE)

    data["case_id"] = case_id
    data["url"] = source_url
    data["jurisdiction"] = "India"
    data["source"] = "Indian Kanoon"

    text_fields = [
        "title",
        "court",
        "date",
        "citation",
        "area_of_law",
        "facts",
        "procedural_history",
        "court_reasoning",
        "final_order",
        "case_summary",
    ]

    list_fields = [
        "keywords",
        "legal_issues",
        "statutes_cited",
        "precedents_cited",
    ]

    for field in text_fields:
        data[field] = normalize_text_field(parsed.get(field, ""))

    for field in list_fields:
        data[field] = to_list_of_strings(parsed.get(field, []))

    # Normalize date to YYYY-MM-DD where possible.
    date_val = data["date"]
    if date_val:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_val)
        if m:
            data["date"] = m.group(0)
        else:
            data["date"] = ""

    data["chunks"] = normalize_chunks(case_id, parsed.get("chunks"), cleaned_text)
    data["court"] = normalize_court_name(data["court"], cleaned_text)
    data["area_of_law"] = infer_area_of_law(cleaned_text, data["area_of_law"])
    data["legal_issues"] = refine_legal_issues(data["legal_issues"], cleaned_text)
    data["procedural_history"] = build_procedural_history(cleaned_text, data["procedural_history"])
    data["court_reasoning"] = refine_court_reasoning(data["court_reasoning"], cleaned_text, data["chunks"])
    data["final_order"] = refine_final_order(data["final_order"], cleaned_text)

    return data


def process_case(pdf_path: Path, output_dir: Path, model: str = MODEL, overwrite: bool = False) -> bool:
    case_id = pdf_path.stem
    output_file = output_dir / f"{case_id}.json"

    if output_file.exists() and not overwrite:
        return False

    raw_text = extract_pdf_text(pdf_path)
    cleaned_text = clean_text(raw_text)

    source_url = f"https://indiankanoon.org/doc/{case_id}/"
    prompt = build_prompt(cleaned_text, case_id, source_url)

    llm_output = call_ollama(prompt, model=model)
    parsed = extract_json_payload(llm_output)
    final_data = enforce_schema(case_id, source_url, cleaned_text, parsed)

    output_file.write_text(json.dumps(final_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Indian Kanoon judgment PDFs to schema JSON with Ollama.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", type=str, default=MODEL)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N PDFs (0 = all)")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted([p for p in input_dir.glob("*.pdf") if p.is_file()])
    if args.limit > 0:
        pdf_files = pdf_files[: args.limit]

    if not pdf_files:
        print(f"No PDFs found in {input_dir}")
        return

    processed = 0
    skipped = 0
    failed = 0

    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        try:
            did_process = process_case(pdf_path, output_dir, model=args.model, overwrite=args.overwrite)
            if did_process:
                processed += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            print(f"[ERROR] {pdf_path.name}: {exc}")

    print(f"Done. processed={processed}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
