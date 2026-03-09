import concurrent.futures
import json
import logging
import os
from pathlib import Path
from tqdm import tqdm
from extract_text import extract_text
from llm_client import convert_judgment_to_json
from config import (
    INPUT_ROOT,
    OUTPUT_ROOT,
    OUTPUT_MODE,
    MAX_WORKERS,
    BATCH_SIZE,
)

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(processName)s %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------
# Helper – write JSON
# ---------------------------------------------------------
def _write_json(case_id: str, data: dict):
    if OUTPUT_MODE == "per_file":
        out_path = OUTPUT_ROOT / f"{case_id}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    else:   # jsonl – one file, line‑by‑line
        out_path = OUTPUT_ROOT / "cases.jsonl"
        with out_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(data, ensure_ascii=False) + "\n")

# ---------------------------------------------------------
# Worker – process ONE PDF
# ---------------------------------------------------------
def _process_one(pdf_path: Path) -> None:
    try:
        raw_text = extract_text(pdf_path)

        # ---- 1️⃣  LLM conversion  ----
        json_obj = convert_judgment_to_json(raw_text)

        # ---- 2️⃣  Enforce case_id (fallback to filename) ----
        case_id = json_obj.get("case_id") or pdf_path.stem
        json_obj["case_id"] = case_id

        # ---- 3️⃣  Persist ----
        _write_json(case_id, json_obj)

        log.info("✅ %s → %s.json", pdf_path.name, case_id)
    except Exception as exc:
        log.exception("❌ Failed on %s: %s", pdf_path.name, exc)

# ---------------------------------------------------------
# Main driver – batch + parallelism
# ---------------------------------------------------------
def main():
    pdf_files = sorted([p for p in INPUT_ROOT.rglob("*.pdf")])
    log.info("Found %d PDF files under %s", len(pdf_files), INPUT_ROOT)

    # Optional: pre‑create JSONL file with a header line (not needed for pure JSONL)
    if OUTPUT_MODE == "jsonl" and (OUTPUT_ROOT / "cases.jsonl").exists():
        os.remove(OUTPUT_ROOT / "cases.jsonl")

    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        list(
            tqdm(
                executor.map(_process_one, pdf_files),
                total=len(pdf_files),
                desc="Processing PDFs",
                unit="pdf",
            )
        )

    log.info("✅ All done – JSON files are in %s", OUTPUT_ROOT)

if __name__ == "__main__":
    main()
