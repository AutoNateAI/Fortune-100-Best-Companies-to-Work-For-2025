# bootstrap_sec_data.py
import requests, json, datetime, time, logging, re
from pathlib import Path
from rapidfuzz import fuzz, process   # pip install rapidfuzz

COMPANIES_FILE = "fortune_100_companies_enriched_with_hq_addr.json"
OUTPUT_FILE    = "company_financials.json"
BASE_URL = "https://data.sec.gov"
BASE_URL_COMPANY_TICKERS = "https://www.sec.gov"
HEADERS  = {"User-Agent": "Your Name <email@example.com>"}

# --- Logging setup with emoji level names ---
class EmojiFormatter(logging.Formatter):
    EMOJIS = {
        logging.DEBUG:    "🔍",
        logging.INFO:     "ℹ️",
        logging.WARNING:  "⚠️",
        logging.ERROR:    "❌",
        logging.CRITICAL: "🔥"
    }
    def format(self, record):
        prefix = self.EMOJIS.get(record.levelno, "")
        record.msg = f"{prefix} {record.msg}"
        return super().format(record)

logger = logging.getLogger("sec_bot")
handler = logging.StreamHandler()
handler.setFormatter(EmojiFormatter("%(asctime)s | %(levelname)s | %(message)s",
                                    "%Y-%m-%d %H:%M:%S"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ----------------------------------------------------------
# Utilities
# ----------------------------------------------------------

def normalize_name(name: str) -> str:
    """
    Lowercase, strip punctuation and common corporate suffixes
    so that 'Adobe Systems Incorporated' ≈ 'Adobe Inc.'
    """
    name = re.sub(r'\b(incorporated|inc|corp|corporation|llc|ltd|plc|group|company)\b',
                  '', name, flags=re.I)
    name = re.sub(r'[^a-z0-9 ]', '', name.lower())
    return ' '.join(name.split())

def load_ticker_map() -> dict:
    """Download the SEC's ticker→CIK map once per run."""
    url = f"{BASE_URL_COMPANY_TICKERS}/files/company_tickers.json"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def get_cik(company_name: str, mapping: dict) -> str:
    """
    Try a strong fuzzy match first (score ≥85). If nothing clears it,
    fall back to a simple substring check inside the SEC title.
    Returns a zero-padded CIK string if a match is found.
    """
    target = normalize_name(company_name)

    # ---- strong fuzzy match ----
    choices = [(normalize_name(v["title"]), k) for k, v in mapping.items()]
    best, score, key = process.extractOne(
        target,
        [c[0] for c in choices],
        scorer=fuzz.token_sort_ratio
    )
    if score >= 85:
        cik_str = str(mapping[str(key)]["cik_str"]).zfill(10)
        logger.debug(f"Fuzzy match: '{company_name}' -> '{mapping[str(key)]['title']}' (score {score})")
        return cik_str

    # ---- fallback: simple substring ----
    for v in mapping.values():
        if target in normalize_name(v["title"]):
            cik_str = str(v["cik_str"]).zfill(10)
            logger.debug(f"Fallback substring match: '{company_name}' -> '{v['title']}'")
            return cik_str

    raise ValueError(f"CIK not found (best fuzzy score {score}) for {company_name}")

def extract_facts(cik: str):
    r = requests.get(f"{BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json",
                     headers=HEADERS)
    r.raise_for_status()
    facts = r.json()["facts"]["us-gaap"]
    cutoff = datetime.date.today().year - 5
    def pick(name):
        items = facts.get(name, {}).get("units", {}).get("USD", [])
        return [{"year": int(i["end"][:4]), "val": i["val"]}
                for i in items if int(i["end"][:4]) >= cutoff]
    return {
        "Revenue": pick("Revenues"),
        "NetIncome": pick("NetIncomeLoss"),
        "OperatingCashFlow": pick("NetCashProvidedByUsedInOperatingActivities"),
        "Assets": pick("Assets"),
        "Liabilities": pick("Liabilities"),
        "Equity": pick("StockholdersEquity")
    }

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------

def main():
    companies = json.load(open(COMPANIES_FILE))
    mapping   = load_ticker_map()
    all_data  = {}
    for c in companies:
        name = c["company"]
        try:
            logger.info(f"Processing {name}")
            cik = get_cik(name, mapping)
            all_data[name] = {
                "cik": cik,
                "financials": extract_facts(cik)
            }
            logger.info(f"✅ Finished {name}")
            time.sleep(0.2)   # SEC courtesy pause
        except Exception as e:
            logger.error(f"Skipping {name}: {e}")
    Path(OUTPUT_FILE).write_text(json.dumps(all_data, indent=2))
    logger.info(f"📁 Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
