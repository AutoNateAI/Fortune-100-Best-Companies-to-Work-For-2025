#!/usr/bin/env python3
"""
Enrich a Fortune 100 JSON with HQ address and coordinates
using Google Places API (New), with colorful logging.
"""

import os
import json
import time
import requests
import logging
from dotenv import load_dotenv
from colorlog import ColoredFormatter

load_dotenv()

INPUT_FILE  = "fortune_100_companies.json"
OUTPUT_FILE = "fortune_100_companies_enriched_with_hq_addr.json"
API_KEY     = os.environ.get("GOOGLE_PLACES_API_KEY")
SLEEP_SECONDS = 0.3   # stay well under free-tier QPS

# ---------- logging setup ----------
LOG_FORMAT = "%(log_color)s%(levelname)-8s%(reset)s  %(message_log_color)s%(message)s"
formatter = ColoredFormatter(
    LOG_FORMAT,
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'bold_red',
    },
    secondary_log_colors={
        'message': {
            'INFO': 'white',
            'DEBUG': 'white',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        }
    },
    style='%'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger("enrich")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
# -----------------------------------

def search_place(company_name):
    """
    Use the Places API (New) text search to get place_id,
    formatted address and location.
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.formattedAddress,places.location"
    }
    payload = {"textQuery": f"{company_name} headquarters"}
    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()
    places = data.get("places", [])
    if not places:
        return None, None, None
    p = places[0]
    return p["id"], p["formattedAddress"], (p["location"]["latitude"], p["location"]["longitude"])

def enrich():
    if not API_KEY:
        logger.critical("❗ Environment variable GOOGLE_PLACES_API_KEY is not set.")
        raise RuntimeError("GOOGLE_PLACES_API_KEY not set.")
    with open(INPUT_FILE, encoding="utf-8") as f:
        companies = json.load(f)

    logger.info(f"🚀 Starting enrichment of {len(companies)} companies…")

    for i, c in enumerate(companies, start=1):
        name = c["company"]
        logger.info(f"🔎 [{i}/{len(companies)}] Searching for: {name}")
        try:
            pid, addr, coords = search_place(name)
            if addr and coords:
                lat, lng = coords
                c["hq_address"] = addr
                c["latitude"] = lat
                c["longitude"] = lng
                logger.info(f"✅  {name}: {addr}  📍({lat:.4f}, {lng:.4f})")
            else:
                c["hq_address"] = None
                c["latitude"] = None
                c["longitude"] = None
                logger.warning(f"⚠️  No match for {name}")
        except Exception as e:
            logger.error(f"💥 Error processing {name}: {e}")
            c["hq_address"] = None
            c["latitude"] = None
            c["longitude"] = None

        time.sleep(SLEEP_SECONDS)  # polite throttling

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)

    logger.info(f"🎉 Enriched data written to {OUTPUT_FILE}")

if __name__ == "__main__":
    enrich()
