# daily_update_sec_data.py
import requests, json, time, logging
from pathlib import Path
from rapidfuzz import process, fuzz

from bootstrap_sec_data import (
    logger, BASE_URL, HEADERS, BASE_URL_COMPANY_TICKERS
)

DATA_FILE = "company_financials.json"

# --- helper: fuzzy + exact CIK lookup -----------------
def get_cik(ticker_or_name: str) -> str:
    """
    Resolve a company name to its 10-digit CIK using the SEC's company_tickers.json.
    Falls back to fuzzy matching if no exact title match.
    """
    r = requests.get(f"{BASE_URL_COMPANY_TICKERS}/files/company_tickers.json", headers=HEADERS)
    r.raise_for_status()
    mapping = r.json()

    # exact title match first
    for v in mapping.values():
        if v["title"].lower() == ticker_or_name.lower():
            return str(v["cik_str"]).zfill(10)

    # fuzzy fallback
    titles = [v["title"] for v in mapping.values()]
    best, score, idx = process.extractOne(
        ticker_or_name, titles, scorer=fuzz.token_sort_ratio
    )
    if score >= 85:
        match = [v for v in mapping.values() if v["title"] == best][0]
        logger.warning(f"⚠️ Using fuzzy match {best} (score {score:.1f}) for {ticker_or_name}")
        return str(match["cik_str"]).zfill(10)
    raise ValueError(f"CIK not found (best fuzzy score {score}) for {ticker_or_name}")

# --- helper: pull latest available values for each metric ----------
def latest_years(cik):
    r = requests.get(f"{BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json", headers=HEADERS)
    r.raise_for_status()
    facts = r.json().get("facts", {}).get("us-gaap", {})
    def pick(name):
        items = facts.get(name, {}).get("units", {}).get("USD", [])
        return {int(i["end"][:4]): i["val"] for i in items}
    return {
        "Revenue": pick("Revenues"),
        "NetIncome": pick("NetIncomeLoss"),
        "OperatingCashFlow": pick("NetCashProvidedByUsedInOperatingActivities"),
        "Assets": pick("Assets"),
        "Liabilities": pick("Liabilities"),
        "Equity": pick("StockholdersEquity")
    }

# --- main daily update loop ---------------------------------------
def main():
    data = json.load(open(DATA_FILE))

    for name, info in data.items():
        logger.info(f"🔄 Checking updates for {name}")
        try:
            # ensure we have a CIK; if missing, attempt lookup again
            cik = info.get("cik")
            if not cik:
                cik = get_cik(name)
                info["cik"] = cik
                logger.info(f"➕ Added missing CIK {cik} for {name}")

            updated = latest_years(cik)
            for metric, vals in updated.items():
                known_years = {v["year"] for v in info["financials"].get(metric, [])}
                for year, val in vals.items():
                    if year not in known_years:
                        logger.info(f"➕ New {metric} {year}: {val}")
                        info["financials"].setdefault(metric, []).append({"year": year, "val": val})

            time.sleep(0.2)   # SEC rate-limit friendly

        except Exception as e:
            logger.error(f"⚠️ Error updating {name}: {e}")

    Path(DATA_FILE).write_text(json.dumps(data, indent=2))
    logger.info(f"💾 File updated: {DATA_FILE}")

if __name__ == "__main__":
    main()
