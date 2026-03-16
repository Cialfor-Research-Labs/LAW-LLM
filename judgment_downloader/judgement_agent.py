import os
import re
import time
import random
import sys
import threading
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

import requests
from playwright.sync_api import sync_playwright


BASE_URL = "https://indiankanoon.org"
SEARCH_URL = f"{BASE_URL}/search/"

DOCTYPES = [
    "supremecourt"
]

YEARS = list(range(2000, 2001))

# Act names to search per doctype
ACT_NAMES = [
    "Aadhaar Act",
    "Academy of Scientific and Innovative Research Act",
    "Acquired Territories Act",
    "Acquisition of Certain Area at Ayodhya Act",
    "Actuaries Act",
    "Administrative Tribunals Act",
    "Administrators General Act",
    "Admiralty Act",
    "Advocates Act",
    "Advocates Welfare Fund Act",
    "African Development Bank Act",
    "African Development Fund Act",
    "Agricultural and Processed Food Products Export Development Authority Act",
    "Agricultural Produce Act",
    "Agriculturists Loans Act",
    "Air Act",
    "Air Force Act",
    "Airports Authority of India Act",
    "Airports Economic Regulatory Authority of India Act",
    "Ajmer Tenancy and Land Records Act",
    "Aligarh Muslim University Act",
    "All India Council for Technical Education Act",
    "All India Institute of Medical Science Act",
    "All India Services Act",
    "Anand Marriage Act",
    "Ancient Monuments and Archaeological Sites and Remains Act",
    "Ancient Monuments Preservation Act",
    "Andhra Pradesh and Madras Act",
    "Andhra Pradesh and Mysore Act",
    "Andhra Pradesh Legislative Council Act",
    "Andhra Pradesh Reorganisation Act",
    "Andhra State Act",
    "Anti Apartheid Act",
    "Anti Hijacking Act",
    "Antiquities and Art Treasures Act",
    "Anusandhan National Research Foundation Act",
    "Apprentices Act",
    "Arbitration and Conciliation Act",
    "Architects Act",
    "Armed Forces Act",
    "Armed Forces Act",
    "Armed Forces Special Powers Act",
    "Armed Forces Special Powers Act",
    "Armed Forces Tribunal Act",
    "Arms Act",
    "Army Act",
    "Army and Air Force Act",
    "Arya Marriage Validation Act",
    "Asian Development Bank Act",
    "Asiatic Society Act",
    "Assam Act",
    "Assam Reorganisation Act",
    "Assam Rifles Act",
    "Assam University Act",
    "Assisted Reproductive Technology Act",
    "Atomic Energy Act",
    "Auroville Foundation Act",
    "Authoritative Texts Act",
    "Babasaheb Bhimrao Ambedkar University Act",
    "Banaras Hindu University Act",
    "Bankers Books Evidence Act",
    "Banking Companies Act",
    "Banking Companies Act",
    "Banking Regulation Act",
    "Banning of Unregulated Deposit Schemes Act",
    "Bengal Agra and Assam Civil Courts Act",
    "Betwa River Board Act",
    "Bharatiya Nagarik Suraksha Sanhita",
    "Bharatiya Nyaya Sanhita",
    "Bharatiya Sakshya Adhiniyam",
    "Bharatiya Vayuyan Adhiniyam",
    "Bhopal Gas Leak Disaster Act",
    "Bihar Reorganisation Act",
    "Bilateral Netting of Qualified Financial Contracts Act",
    "Biological Diversity Act",
    "Black Money and Imposition of Tax Act",
    "Bombay Reorganisation Act",
    "Bonded Labour System Act",
    "Border Security Force Act",
    "Bureau of Indian Standards Act",
    "Cable Television Networks Act",
    "Cantonments Act",
    "Carriage by Air Act",
    "Carriage by Road Act",
    "Central Agricultural University Act",
    "Central Excise Act",
    "Central Goods and Services Tax Act",
    "Central Industrial Security Force Act",
    "Central Reserve Police Force Act",
    "Central Sales Tax Act",
    "Central Universities Act",
    "Central Vigilance Commission Act",
    "Chartered Accountants Act",
    "Chemical Weapons Convention Act",
    "Child and Adolescent Labour Act",
    "Chit Funds Act",
    "Cigarettes and Other Tobacco Products Act",
    "Cinematograph Act",
    "Citizenship Act",
    "Civil Liability for Nuclear Damage Act",
    "Clinical Establishments Act",
    "Co operative Societies Act",
    "Coal Bearing Areas Act",
    "Coal Mines Act",
    "Coast Guard Act",
    "Code of Civil Procedure",
    "Code on Social Security",
    "Code on Wages",
    "Coffee Act",
    "Coinage Act",
    "Commercial Courts Act",
    "Commissions of Inquiry Act",
    "Companies Act",
    "Competition Act",
    "Conservation of Foreign Exchange and Prevention of Smuggling Activities Act",
    "Consumer Protection Act",
    "Contempt of Courts Act",
    "Copyright Act",
    "Criminal Procedure Act",
    "Customs Act",
    "Customs Tariff Act",
    "Dadra and Nagar Haveli and Daman and Diu Act",
    "Dam Safety Act",
    "Damodar Valley Corporation Act",
    "Delhi Development Act",
    "Delhi High Court Act",
    "Delhi Municipal Corporation Act",
    "Delhi Police Act",
    "Delhi Special Police Establishment Act",
    "Delimitation Act",
    "Dentists Act",
    "Deposit Insurance and Credit Guarantee Corporation Act",
    "Depositories Act",
    "Designs Act",
    "Digital Personal Data Protection Act",
    "Disaster Management Act",
    "Dissolution of Muslim Marriages Act",
    "Divorce Act",
    "Dock Workers Act",
    "Dowry Prohibition Act",
    "Drugs and Cosmetics Act",
    "Drugs and Magic Remedies Act",
    "Economic Offences Act",
    "Electricity Act",
    "Emigration Act",
    "Employees Provident Funds and Miscellaneous Provisions Act",
    "Enemy Property Act",
    "Energy Conservation Act",
    "Environment Act",
    "Epidemic Diseases Act",
    "Essential Commodities Act",
    "Explosive Substances Act",
    "Explosives Act",
    "Extradition Act",
    "Factoring Regulation Act",
    "Family Courts Act",
    "Fatal Accidents Act",
    "Food Safety and Standards Act",
    "Foreign Contribution Act",
    "Foreign Exchange Management Act",
    "Foreign Marriage Act",
    "Foreign Trade Act",
    "Forward Contracts Act",
    "Fugitive Economic Offenders Act",
    "General Clauses Act",
    "General Insurance Business Act",
    "Geographical Indications of Goods Act",
    "Goods and Services Tax Act",
    "Government of National Capital Territory of Delhi Act",
    "Gram Nyayalayas Act",
    "Guardians and Wards Act",
    "Haj Committee Act",
    "Hindu Adoptions and Maintenance Act",
    "Hindu Marriage Act",
    "Hindu Minority and Guardianship Act",
    "Hindu Succession Act",
    "Human Immunodeficiency Virus and Acquired Immune Deficiency Syndrome Act",
    "Illegal Migrants Act",
    "Immoral Traffic Act",
    "Income tax Act",
    "Indian Christian Marriage Act",
    "Indian Contract Act",
    "Indian Easements Act",
    "Indian Forest Act",
    "Indian Penal Code",
    "Indian Ports Act",
    "Indian Stamp Act",
    "Indian Succession Act",
    "Indian Trust Act",
    "Industrial Disputes Act",
    "Industrial Relations Code",
    "Industries Act",
    "Information Technology Act",
    "Inland Vessels Act",
    "Insecticides Act",
    "Insolvency and Bankruptcy Code",
    "Insurance Act",
    "Insurance Regulatory and Development Authority Act",
    "Integrated Goods and Services Tax Act",
    "Inter State River Water Disputes Act",
    "Jammu and Kashmir Reorganisation Act",
    "Juvenile Justice Act",
    "Land Acquisition Act",
    "Legal Metrology Act",
    "Legal Services Authorities Act",
    "Life Insurance Corporation Act",
    "Limitation Act",
    "Limited Liability Partnership Act",
    "Lokpal and Lokayuktas Act",
    "Mahatma Gandhi National Rural Employment Guarantee Act",
    "Maintenance and Welfare of Parents and Senior Citizens Act",
    "Major Port Authorities Act",
    "Marine Insurance Act",
    "Married Womens Property Act",
    "Mediation Act",
    "Medical Termination of Pregnancy Act",
    "Mental Healthcare Act",
    "Merchant Shipping Act",
    "Micro Small and Medium Enterprises Development Act",
    "Mines and Minerals Act",
    "Motor Vehicles Act",
    "Multi State Co operative Societies Act",
    "Muslim Personal Law Application Act",
    "Muslim Women Act",
    "Narcotic Drugs and Psychotropic Substances Act",
    "National Bank for Agriculture and Rural Development Act",
    "National Food Security Act",
    "National Green Tribunal Act",
    "National Highways Act",
    "National Highways Authority of India Act",
    "National Investigation Agency Act",
    "National Medical Commission Act",
    "National Security Act",
    "Negotiable Instruments Act",
    "Occupational Safety Health and Working Conditions Code",
    "Official Languages Act",
    "Official Secrets Act",
    "Parsi Marriage and Divorce Act",
    "Passports Act",
    "Patents Act",
    "Payment and Settlement Systems Act",
    "Pension Fund Regulatory and Development Authority Act",
    "Petroleum Act",
    "Petroleum and Natural Gas Regulatory Board Act",
    "Pharmacy Act",
    "Places of Worship Act",
    "Prevention of Corruption Act",
    "Prevention of Damage to Public Property Act",
    "Prevention of Money Laundering Act",
    "Prevention of Terrorism Act",
    "Prisoners Act",
    "Prohibition of Benami Property Transactions Act",
    "Prohibition of Child Marriage Act",
    "Protection of Children from Sexual Offences Act",
    "Protection of Human Rights Act",
    "Protection of Women from Domestic Violence Act",
    "Public Debt Act",
    "Public Examinations Act",
    "Public Liability Insurance Act",
    "Public Premises Act",
    "Punjab Reorganisation Act",
    "Railway Claims Tribunal Act",
    "Railways Act",
    "Real Estate Act",
    "Recovery Of Debts And Bankruptcy Act",
    "Registration Act",
    "Rehabilitation Council of India Act",
    "Representation of People Act",
    "Representation of People Act",
    "Reserve Bank of India Act",
    "Right of Children to Free and Compulsory Education Act",
    "Right to Fair Compensation and Transparency in Land Acquisition Rehabilitation and Resettlement Act",
    "Right to Information Act",
    "Rights of Persons with Disabilities Act",
    "Road Transport Corporations Act",
    "SAARC Convention Act",
    "Sashastra Seema Bal Act",
    "Scheduled Castes and Scheduled Tribes Act",
    "Scheduled Tribes and Other Traditional Forest Dwellers Act",
    "Securities and Exchange Board of India Act",
    "Securities Contracts Act",
    "Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act",
    "Seeds Act",
    "Sexual Harassment of Women at Workplace Act",
    "Sikh Gurdwaras Act",
    "Slum Areas Act",
    "Societies Registration Act",
    "Special Economic Zones Act",
    "Special Marriage Act",
    "Specific Relief Act",
    "Surrogacy Act",
    "Telecommunications Act",
    "Trade Marks Act",
    "Transfer of Property Act",
    "Transgender Persons Act",
    "Transplantation of Human Organs and Tissues Act",
    "Tribunals Reforms Act",
    "Unlawful Activities Act",
    "University Grants Commission Act",
    "Water Act",
    "Wealth tax Act",
    "Wild Life Act",
    "Women s and Children s Institutions Act",
]

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

import calendar


def build_act_url(doctype: str, act_name: str, page_num: int = 0) -> str:
    """Build Indian Kanoon URL with quoted act name in formInput and doctype filter, no dates."""
    encoded_term = quote_plus(f'"{act_name}"')
    base = (
        f"{SEARCH_URL}"
        f"?formInput={encoded_term}"       # formInput="Arbitration and Conciliation Act 1996"
        f"&filters=doctypes%3A+{doctype}"  # filters=doctypes: supremecourt
    )
    if page_num > 0:
        base += f"&pagenum={page_num}"
    return base


def paginate_act(page, doctype: str, act_name: str) -> list[str]:
    """Paginate all results for a single act name search. Returns raw case URLs."""
    label = f"{doctype}/{act_name[:40]}"
    case_links: list[str] = []
    page_num = 0

    while True:
        url = build_act_url(doctype, act_name, page_num)

        if page_num == 0:
            print(f"\n=================================")
            print(f"  Searching: {act_name}")
            print(f"  {url}")
            print(f"=================================")

        page.goto(url, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(random.uniform(1.5, 3.0))

        results = page.locator("a[href*='/docfragment/']")
        count = results.count()
        print(f"  [{label}] Page {page_num + 1}: {count} links")

        if count == 0:
            break

        for idx in range(count):
            href = results.nth(idx).get_attribute("href")
            if href:
                case_links.append(to_absolute_url(href))

        if count < RESULTS_PER_PAGE:
            break
        page_num += 1

    print(f"  [{label}] Subtotal: {len(case_links)} links")
    return case_links


def collect_all_case_links_for_doctype(page, doctype: str) -> list[str]:
    """Scrape each Act Name and deduplicate results by case_id."""
    all_links: list[str] = []

    for act_name in ACT_NAMES:
        links = paginate_act(page, doctype, act_name)
        all_links.extend(links)

    print(f"\n[{doctype}] Raw links across all acts: {len(all_links)}")

    # Deduplicate by case_id
    seen_case_ids: set[str] = set()
    unique_case_links: list[str] = []

    for case_url in all_links:
        case_id = extract_case_id(case_url)
        if case_id and case_id not in seen_case_ids:
            seen_case_ids.add(case_id)
            unique_case_links.append(case_url)

    print(f"[{doctype}] Unique case links after dedup: {len(unique_case_links)}")
    return unique_case_links


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


def save_case_links_for_doctype(doctype: str, case_links: list[str]) -> str:
    links_file = f"case_links_{doctype}.txt"
    with open(links_file, "w", encoding="utf-8") as f:
        for link in case_links:
            f.write(link + "\n")
    return links_file


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
                folder = os.path.join(DOWNLOAD_ROOT_DIR, doctype)
                os.makedirs(folder, exist_ok=True)

                full_case_links = collect_all_case_links_for_doctype(page, doctype)
                links_file = save_case_links_for_doctype(doctype, full_case_links)

                print(f"[{doctype}] Saved links file: {links_file}")
                print(f"[{doctype}] Total downloadable case links found: {len(full_case_links)}")

                if not full_case_links:
                    continue

                while True:
                    approval = input(
                        f"Start downloading for '{doctype}'? "
                        "Type yes/no: "
                    ).strip().lower()
                    if approval in {"yes", "no"}:
                        break
                    print("Please type exactly: yes or no")

                if approval == "no":
                    print(f"[{doctype}] Skipped by user.")
                    continue

                successes = download_cases_multithreaded(
                    doctype=doctype,
                    year=0,
                    folder=folder,
                    full_case_links=full_case_links,
                    starting_successful_downloads=successful_downloads,
                )
                successful_downloads += successes
                print(f"[{doctype}] Successful downloads: {successes}")

            print(f"\nFinished. Total successful PDF downloads: {successful_downloads}")
            browser.close()
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()


if __name__ == "__main__":
    run_agent()
