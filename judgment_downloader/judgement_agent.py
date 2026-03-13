import os
import re
import time
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

import requests
from playwright.sync_api import sync_playwright


BASE_URL = "https://indiankanoon.org"
SEARCH_URL = f"{BASE_URL}/search/"

DOCTYPES = [
    "supremecourt", "scorders", "allahabad", "andhra", "hyderabad", "amravati", "bombay", "kolkata", "kolkata_app", "chattisgarh", "delhi", "delhiorders", "gauhati", "gujarat", "himachal_pradesh", "jammu", "srinagar", "jharkhand", "karnataka", "kerala", "madhyapradesh", "manipur", "meghalaya", "chennai", "orissa", "patna", "patna_orders", "punjab", "jaipur", "jodhpur", "sikkim", "uttaranchal", "tripura", "telangana"
]

YEARS = list(range(1950, 2027))

RESULTS_PER_PAGE = 10
PAUSE_AFTER_DOWNLOADS = 50
PAUSE_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 60

DOWNLOAD_ROOT_DIR = "judgements"
FAILED_FILE = "failed_cases.txt"
LOG_DIR = "logs"

thread_local = threading.local()
failed_file_lock = threading.Lock()


def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "", name).strip().replace("  ", " ")


def to_absolute_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href.replace("docfragment", "doc")
    return f"{BASE_URL}{href}".replace("docfragment", "doc")


class TeeStream:
    def __init__(self, console_stream, log_stream):
        self.console_stream = console_stream
        self.log_stream = log_stream

    def write(self, data):
        self.console_stream.write(data)
        self.log_stream.write(data)

    def flush(self):
        self.console_stream.flush()
        self.log_stream.flush()


def setup_terminal_logging() -> tuple[str, object, object, object]:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"judgement_agent_{time.strftime('%Y%m%d_%H%M%S')}.log")

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    sys.stdout = TeeStream(original_stdout, log_file)
    sys.stderr = TeeStream(original_stderr, log_file)
    print(f"Logging terminal output to: {log_path}")

    return log_path, log_file, original_stdout, original_stderr


def get_worker_count() -> int:
    # Single thread to avoid rate limiting
    return 1


def get_thread_session() -> requests.Session:
    session = getattr(thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "*/*",
            }
        )
        thread_local.session = session
    return session


def append_failed(doctype: str, year: int, case_url: str, reason: str) -> None:
    with failed_file_lock:
        with open(FAILED_FILE, "a", encoding="utf-8") as failed:
            failed.write(f"{doctype}\t{year}\t{case_url}\t{reason}\n")


def extract_case_id(doc_url: str) -> str | None:
    match = re.search(r"/doc/(\d+)", doc_url)
    return match.group(1) if match else None


def extract_pdf_url_from_case_html(case_html: str, case_url: str) -> str | None:
    patterns = [
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*Get in PDF\s*</a>',
        r'<a[^>]+href=["\']([^"\']*type=pdf[^"\']*)["\']',
        r'<a[^>]+href=["\']([^"\']*/pdf/[^"\']*)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, case_html, flags=re.IGNORECASE)
        if match:
            return to_absolute_url(match.group(1))

    case_id = extract_case_id(case_url)
    if case_id:
        return f"{BASE_URL}/doc/{case_id}/?type=pdf"
    return None


def case_links_file_for_doctype_year(doctype: str, year: int) -> str:
    return f"case_links_{doctype}_{year}.txt"


def save_case_links_for_doctype_year(doctype: str, year: int, case_links: list[str]) -> str:
    links_file = case_links_file_for_doctype_year(doctype, year)
    with open(links_file, "w", encoding="utf-8") as f:
        for link in case_links:
            f.write(link + "\n")
    return links_file


def collect_full_case_links_for_doctype_year(page, doctype: str, year: int) -> list[str]:
    case_links = collect_case_links_from_search(page, doctype, year)
    print(f"[{doctype} {year}] Total case links found: {len(case_links)}")

    # Remove duplicates based on case_id
    seen_case_ids: set[str] = set()
    unique_case_links: list[str] = []

    for case_url in case_links:
        case_id = extract_case_id(case_url)
        if case_id and case_id not in seen_case_ids:
            seen_case_ids.add(case_id)
            unique_case_links.append(case_url)

    return unique_case_links


def collect_case_links_from_search(page, doctype: str, year: int) -> list[str]:
    query = f"doctypes:{doctype} year:{year}"
    case_links: list[str] = []

    print("\n=================================")
    print(f"Searching doctype: {doctype}, year: {year}")
    print(f"Query: {query}")
    print("=================================")

    page_num = 0
    while True:
        if page_num == 0:
            url = f"{SEARCH_URL}?formInput={quote_plus(query)}"
        else:
            url = f"{SEARCH_URL}?formInput={quote_plus(query)}&pagenum={page_num}"
        
        page.goto(url, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(random.uniform(1.5, 3.0))

        results = page.locator("a[href*='/docfragment/']")
        count = results.count()
        print(f"[{doctype} {year}] Page {page_num + 1}: {count} results")

        if count == 0:
            break

        for idx in range(count):
            href = results.nth(idx).get_attribute("href")
            if href:
                case_links.append(to_absolute_url(href))

        if count < RESULTS_PER_PAGE:
            break
        page_num += 1

    return case_links



def download_pdf_from_case_page(case_url: str, folder: str, doctype: str, year: int) -> bool:
    case_id = extract_case_id(case_url)
    if not case_id:
        return False

    pdf_file = os.path.join(folder, f"{case_id}.pdf")
    if os.path.exists(pdf_file):
        print(f"Already exists: {pdf_file}")
        return False

    pdf_url = case_url + '&type=pdf'

    session = get_thread_session()

    for attempt in range(3):
        try:
            pdf_res = session.get(pdf_url, timeout=REQUEST_TIMEOUT_SECONDS)
            pdf_res.raise_for_status()
            content_type = (pdf_res.headers.get("Content-Type") or "").lower()
            if "pdf" not in content_type and not pdf_res.content.startswith(b"%PDF"):
                append_failed(doctype, year, case_url, "non_pdf_response")
                return False

            temp_file = f"{pdf_file}.part"
            with open(temp_file, "wb") as f:
                f.write(pdf_res.content)
            os.replace(temp_file, pdf_file)
            print(f"Downloaded: {pdf_file}")
            time.sleep(2)  # Small delay between downloads
            return True
        except Exception as exc:
            if attempt < 2:
                time.sleep(2)
            else:
                append_failed(doctype, year, case_url, f"download_error:{exc}")

    return False


def download_cases_multithreaded(
    doctype: str,
    year: int,
    folder: str,
    full_case_links: list[str],
    starting_successful_downloads: int,
) -> int:
    workers = get_worker_count()
    print(f"[{doctype} {year}] Starting multithreaded downloads with {workers} threads")

    successful_for_doctype_year = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_case = {
            executor.submit(download_pdf_from_case_page, case_url, folder, doctype, year): case_url
            for case_url in full_case_links
        }

        for future in as_completed(future_to_case):
            try:
                downloaded = future.result()
                if downloaded:
                    successful_for_doctype_year += 1
                    total_success = starting_successful_downloads + successful_for_doctype_year
                    if total_success > 0 and total_success % PAUSE_AFTER_DOWNLOADS == 0:
                        print(
                            f"Downloaded {total_success} files. "
                            f"Sleeping for {PAUSE_SECONDS} seconds..."
                        )
                        time.sleep(PAUSE_SECONDS)
            except Exception as exc:
                failed_case = future_to_case[future]
                append_failed(doctype, year, failed_case, f"thread_error:{exc}")

    return successful_for_doctype_year


def run_agent() -> None:
    _, log_file, original_stdout, original_stderr = setup_terminal_logging()
    os.makedirs(DOWNLOAD_ROOT_DIR, exist_ok=True)
    successful_downloads = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()

            for doctype in DOCTYPES:
                for year in YEARS:
                    folder = os.path.join(DOWNLOAD_ROOT_DIR, doctype, str(year))
                    os.makedirs(folder, exist_ok=True)

                    full_case_links = collect_full_case_links_for_doctype_year(page, doctype, year)
                    links_file = save_case_links_for_doctype_year(doctype, year, full_case_links)

                    print(f"[{doctype} {year}] Saved links file: {links_file}")
                    print(f"[{doctype} {year}] Total downloadable case links found: {len(full_case_links)}")

                    if not full_case_links:
                        continue

                    while True:
                        approval = input(
                            f"Start downloading for '{doctype} {year}'? "
                            "Type yes/no: "
                        ).strip().lower()
                        if approval in {"yes", "no"}:
                            break
                        print("Please type exactly: yes or no")

                    if approval == "no":
                        print(f"[{doctype} {year}] Skipped by user.")
                        continue

                    successes = download_cases_multithreaded(
                        doctype=doctype,
                        year=year,
                        folder=folder,
                        full_case_links=full_case_links,
                        starting_successful_downloads=successful_downloads,
                    )
                    successful_downloads += successes
                    print(f"[{doctype} {year}] Successful downloads: {successes}")

            print(f"\nFinished. Total successful PDF downloads: {successful_downloads}")
            browser.close()
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()


if __name__ == "__main__":
    run_agent()
