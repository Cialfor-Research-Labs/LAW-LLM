# ---------------------------------------------------------
#  USER‑CONFIGURABLE SETTINGS
# ---------------------------------------------------------

from pathlib import Path

# -----------------------------------------------------------------
# 1️⃣  LLM SETTINGS  (keep the same unless you want another model)
# -----------------------------------------------------------------
LLM_PROVIDER = "openai"
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.0

# -----------------------------------------------------------------
# 2️⃣  INPUT / OUTPUT SETTINGS
# -----------------------------------------------------------------
# 👉 Change this line – point to the folder that actually holds the PDFs
INPUT_ROOT = Path("../judgements")          # <‑‑  <-- HERE
OUTPUT_ROOT = Path("../json_out")           # where you want the JSON files
OUTPUT_ROOT.mkdir(exist_ok=True)

OUTPUT_MODE = "per_file"   # "per_file" | "jsonl"
# -----------------------------------------------------------------
# 3️⃣  PERFORMANCE SETTINGS
# -----------------------------------------------------------------
MAX_WORKERS = 8          # adjust to your CPU / RAM
BATCH_SIZE = 12
MAX_RETRIES = 5
