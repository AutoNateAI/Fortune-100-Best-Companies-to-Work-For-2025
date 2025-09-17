#!/usr/bin/env python3
"""
Extract Fortune 100 'Best Places to Work' entries from the saved HTML page
into a JSON file.
"""

from bs4 import BeautifulSoup
import json

# --- Configuration ----------------------------------------------------------
HTML_INPUT  = "fortune_100_companies_to_work_at.html"   # your saved html file
JSON_OUTPUT = "fortune_100_companies.json"              # output file name
# ----------------------------------------------------------------------------

def extract_companies(html_path):
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    companies = []
    for row in soup.select("div.row.company.small.no-margin-top.list-filter-show"):
        rank        = int(row.select_one(".rank.large").get_text(strip=True))
        company     = row.select_one("a.link.h5").get_text(strip=True)
        industry    = row.select_one("ul.industry li").get_text(strip=True)
        location    = row.select_one("ul.location li").get_text(strip=True)
        profile_url = row.select_one("ul.review-link a")["href"]
        quote       = row.select_one("div.quote").get_text(strip=True)
        image_url   = row.select_one("img.image")["src"]

        companies.append({
            "rank": rank,
            "company": company,
            "industry": industry,
            "location": location,
            "profile_url": profile_url,
            "employee_quote": quote,
            "image_url": image_url
        })
    return companies

if __name__ == "__main__":
    data = extract_companies(HTML_INPUT)
    with open(JSON_OUTPUT, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
    print(f"✅ Extracted {len(data)} entries to {JSON_OUTPUT}")
