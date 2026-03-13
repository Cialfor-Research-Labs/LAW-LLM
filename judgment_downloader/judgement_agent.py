import os
import re
import time
import random
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright


BASE_URL = "https://indiankanoon.org"
SEARCH_URL = f"{BASE_URL}/search/"
DOCTYPES_FILTER = "doctypes:judgments"

RESULTS_PER_PAGE = 10
PAUSE_AFTER_DOWNLOADS = 150
PAUSE_SECONDS = 30

DOWNLOAD_ROOT_DIR = "judgements"
FAILED_FILE = "failed_cases.txt"

ACT_NAMES = [
    "Indian Evidence Act",
    "Consumer Protection Act",
    "Code of Civil Procedure",
]


def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "", name).strip().replace("  ", " ")


def to_absolute_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return f"{BASE_URL}{href}"


def extract_case_id(doc_url: str) -> str | None:
    match = re.search(r"/doc/(\d+)/", doc_url)
    return match.group(1) if match else None


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


def download_pdf_from_case_page(page, case_url: str, act_folder: str) -> bool:
    case_id = extract_case_id(case_url)
    if not case_id:
        return False

    pdf_file = os.path.join(act_folder, f"{case_id}.pdf")
    if os.path.exists(pdf_file):
        print(f"Already exists: {pdf_file}")
        return False

    page.goto(case_url, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(random.uniform(1.0, 2.0))

    pdf_button = page.locator("text=Get in PDF")
    if pdf_button.count() == 0:
        print(f"No PDF button found: {case_url}")
        return False

    for attempt in range(3):
        try:
            with page.expect_download(timeout=60000) as download_info:
                pdf_button.first.click()
            download = download_info.value
            download.save_as(pdf_file)
            print(f"Downloaded: {pdf_file}")
            return True
        except Exception:
            if attempt < 2:
                print("Retrying PDF download...")
                time.sleep(3)

    return False


def run_agent() -> None:
    os.makedirs(DOWNLOAD_ROOT_DIR, exist_ok=True)
    successful_downloads = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
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

            for full_case_url in full_case_links:
                try:
                    downloaded = download_pdf_from_case_page(page, full_case_url, act_folder)
                    if downloaded:
                        successful_downloads += 1

                    if successful_downloads > 0 and successful_downloads % PAUSE_AFTER_DOWNLOADS == 0:
                        print(
                            f"Downloaded {successful_downloads} files. "
                            f"Sleeping for {PAUSE_SECONDS} seconds..."
                        )
                        time.sleep(PAUSE_SECONDS)

                    page.goto("about:blank")
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as exc:
                    print(f"Error processing case page {full_case_url}: {exc}")
                    with open(FAILED_FILE, "a", encoding="utf-8") as failed:
                        failed.write(f"{act_name}\t{full_case_url}\n")

        print(f"\nFinished. Total successful PDF downloads: {successful_downloads}")
        browser.close()


if __name__ == "__main__":
    run_agent()
