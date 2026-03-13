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
DOCTYPES_FILTER = "doctypes:judgments"

RESULTS_PER_PAGE = 10
PAUSE_AFTER_DOWNLOADS = 150
PAUSE_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 60

DOWNLOAD_ROOT_DIR = "judgements"
FAILED_FILE = "failed_cases.txt"
LOG_DIR = "logs"

ACT_NAMES = [
    "Indian Evidence Act",
    "Consumer Protection Act",
    "Code of Civil Procedure",
]

thread_local = threading.local()
failed_file_lock = threading.Lock()


def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "", name).strip().replace("  ", " ")


def to_absolute_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return f"{BASE_URL}{href}"


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
    # Network-heavy workload: use multiple threads, bounded for stability.
    cpu_count = os.cpu_count() or 4
    return max(4, min(32, cpu_count * 4))


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


def append_failed(act_name: str, case_url: str, reason: str) -> None:
    with failed_file_lock:
        with open(FAILED_FILE, "a", encoding="utf-8") as failed:
            failed.write(f"{act_name}\t{case_url}\t{reason}\n")


def extract_case_id(doc_url: str) -> str | None:
    match = re.search(r"/doc/(\d+)/", doc_url)
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


def case_links_file_for_act(act_name: str) -> str:
    safe_act_name = sanitize_folder_name(act_name).lower().replace(" ", "_")
    return f"case_link_{safe_act_name}.txt"


def save_case_links_for_act(act_name: str, case_links: list[str]) -> str:
    links_file = case_links_file_for_act(act_name)
    with open(links_file, "w", encoding="utf-8") as f:
        for link in case_links:
            f.write(link + "\n")
    return links_file


def collect_full_case_links_for_act(page, act_name: str) -> list[str]:
    result_pages = search_act_and_collect_result_pages(page, act_name)
    print(f"[{act_name}] Total result pages found: {len(result_pages)}")

    full_case_links: list[str] = []
    seen_case_ids: set[str] = set()

    for result_page in result_pages:
        try:
            full_case_url = get_full_case_link_from_result_page(page, result_page)
            if not full_case_url:
                continue

            case_id = extract_case_id(full_case_url)
            if not case_id or case_id in seen_case_ids:
                continue

            seen_case_ids.add(case_id)
            full_case_links.append(full_case_url)
        except Exception as exc:
            print(f"Error while collecting link {result_page}: {exc}")
            with open(FAILED_FILE, "a", encoding="utf-8") as failed:
                failed.write(f"{act_name}\t{result_page}\n")

    return full_case_links


def search_act_and_collect_result_pages(page, act_name: str) -> list[str]:
    query = f'"{act_name}"'
    # Keep doctypes filter inside formInput so results are restricted to judgments.
    query_with_filter = f"{query} {DOCTYPES_FILTER}"
    result_pages: list[str] = []

    print("\n=================================")
    print("Searching act:", act_name)
    print("Query:", query_with_filter)
    print("=================================")
    first_url = f"{SEARCH_URL}?formInput={quote_plus(query_with_filter)}"
    page.goto(first_url, timeout=60000)
    page.wait_for_load_state("domcontentloaded")

    page_num = 0
    while True:
        if page_num > 0:
            paged_url = (
                f"{SEARCH_URL}?formInput={quote_plus(query_with_filter)}"
                f"&pagenum={page_num}"
            )
            page.goto(paged_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

        time.sleep(random.uniform(1.5, 3.0))

        results = page.locator(".result_title a")
        count = results.count()
        print(f"[{act_name}] Page {page_num + 1}: {count} results")

        if count == 0:
            break

        for idx in range(count):
            href = results.nth(idx).get_attribute("href")
            if href:
                result_pages.append(to_absolute_url(href))

        if count < RESULTS_PER_PAGE:
            break
        page_num += 1

    return result_pages


def get_full_case_link_from_result_page(page, result_page_url: str) -> str | None:
    page.goto(result_page_url, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(random.uniform(1.0, 2.0))

    # The result page usually has a case-title hyperlink (A vs B) pointing to /doc/<id>/.
    case_links = page.locator("a[href*='/doc/']")
    for idx in range(case_links.count()):
        href = case_links.nth(idx).get_attribute("href")
        text = (case_links.nth(idx).inner_text() or "").strip()
        if not href:
            continue
        if " vs " in text.lower() or " v. " in text.lower() or href.startswith("/doc/"):
            return to_absolute_url(href)

    html = page.content()
    match = re.search(r'href="(/doc/\d+/)"', html)
    if match:
        return to_absolute_url(match.group(1))
    return None


def download_pdf_from_case_page(case_url: str, act_folder: str, act_name: str) -> bool:
    case_id = extract_case_id(case_url)
    if not case_id:
        return False

    pdf_file = os.path.join(act_folder, f"{case_id}.pdf")
    if os.path.exists(pdf_file):
        print(f"Already exists: {pdf_file}")
        return False

    session = get_thread_session()

    for attempt in range(3):
        try:
            case_res = session.get(case_url, timeout=REQUEST_TIMEOUT_SECONDS)
            case_res.raise_for_status()
            pdf_url = extract_pdf_url_from_case_html(case_res.text, case_url)
            if not pdf_url:
                append_failed(act_name, case_url, "pdf_url_not_found")
                return False

            pdf_res = session.get(pdf_url, timeout=REQUEST_TIMEOUT_SECONDS)
            pdf_res.raise_for_status()
            content_type = (pdf_res.headers.get("Content-Type") or "").lower()
            if "pdf" not in content_type and not pdf_res.content.startswith(b"%PDF"):
                append_failed(act_name, case_url, "non_pdf_response")
                return False

            temp_file = f"{pdf_file}.part"
            with open(temp_file, "wb") as f:
                f.write(pdf_res.content)
            os.replace(temp_file, pdf_file)
            print(f"Downloaded: {pdf_file}")
            return True
        except Exception as exc:
            if attempt < 2:
                time.sleep(2)
            else:
                append_failed(act_name, case_url, f"download_error:{exc}")

    return False


def download_cases_multithreaded(
    act_name: str,
    act_folder: str,
    full_case_links: list[str],
    starting_successful_downloads: int,
) -> int:
    workers = get_worker_count()
    print(f"[{act_name}] Starting multithreaded downloads with {workers} threads")

    successful_for_act = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_case = {
            executor.submit(download_pdf_from_case_page, case_url, act_folder, act_name): case_url
            for case_url in full_case_links
        }

        for future in as_completed(future_to_case):
            try:
                downloaded = future.result()
                if downloaded:
                    successful_for_act += 1
                    total_success = starting_successful_downloads + successful_for_act
                    if total_success > 0 and total_success % PAUSE_AFTER_DOWNLOADS == 0:
                        print(
                            f"Downloaded {total_success} files. "
                            f"Sleeping for {PAUSE_SECONDS} seconds..."
                        )
                        time.sleep(PAUSE_SECONDS)
            except Exception as exc:
                failed_case = future_to_case[future]
                append_failed(act_name, failed_case, f"thread_error:{exc}")

    return successful_for_act


def run_agent() -> None:
    _, log_file, original_stdout, original_stderr = setup_terminal_logging()
    os.makedirs(DOWNLOAD_ROOT_DIR, exist_ok=True)
    successful_downloads = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()

            for act_name in ACT_NAMES:
                safe_act_name = sanitize_folder_name(act_name)
                act_folder = os.path.join(DOWNLOAD_ROOT_DIR, safe_act_name)
                os.makedirs(act_folder, exist_ok=True)

                full_case_links = collect_full_case_links_for_act(page, act_name)
                links_file = save_case_links_for_act(act_name, full_case_links)

                print(f"[{act_name}] Saved links file: {links_file}")
                print(f"[{act_name}] Total downloadable case links found: {len(full_case_links)}")

                if not full_case_links:
                    continue

                while True:
                    approval = input(
                        f"Start downloading for '{act_name}'? "
                        "Type yes/no: "
                    ).strip().lower()
                    if approval in {"yes", "no"}:
                        break
                    print("Please type exactly: yes or no")

                if approval == "no":
                    print(f"[{act_name}] Skipped by user.")
                    continue

                act_successes = download_cases_multithreaded(
                    act_name=act_name,
                    act_folder=act_folder,
                    full_case_links=full_case_links,
                    starting_successful_downloads=successful_downloads,
                )
                successful_downloads += act_successes
                print(f"[{act_name}] Successful downloads: {act_successes}")

            print(f"\nFinished. Total successful PDF downloads: {successful_downloads}")
            browser.close()
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()


if __name__ == "__main__":
    run_agent()
