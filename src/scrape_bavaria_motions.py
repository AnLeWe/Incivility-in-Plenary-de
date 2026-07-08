"""
Scrape motion metadata from the Bavarian Landtag document portal.

Source: https://www.bayern.landtag.de/parlament/dokumente/drucksachen/
  ?dokumentenart=Drucksache&wp={wp}&page={n}

Covers WP 16 (2008–2013), WP 17 (2013–2018), WP 18 (2018–2023).
20 documents per page; WP 16 ~19k, WP 17 ~42k, WP 18 ~30k docs.

Output: DATA_ROOT/raw/by_motions_metadata.csv
"""

import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://www.bayern.landtag.de/parlament/dokumente/drucksachen/"
BASE_PARAMS = {"dokumentenart": "Drucksache"}

WAHLPERIODEN = [16, 17, 18]
DELAY = 1.0  # seconds between requests — be polite
OUT_PATH = Path(os.environ["DATA_ROOT"]) / "raw" / "by_motions_metadata.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research scraper; anna.werner@uni-konstanz.de)"
}


def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total page count from pagination or result count text."""
    # "Treffer 1 - 20 von 19774"
    text = soup.get_text()
    match = re.search(r"Treffer\s+\d+\s*-\s*\d+\s+von\s+([\d.]+)", text)
    if match:
        total = int(match.group(1).replace(".", ""))
        return (total + 19) // 20  # 20 per page
    return 1


def parse_page(soup: BeautifulSoup, wp: int) -> list[dict]:
    records = []

    # Each document is anchored by an <h4> containing the doc number link
    for h4 in soup.find_all("h4"):
        a = h4.find("a", href=True)
        if not a:
            continue

        # "Drucksache Nr. 16/1234 vom 01.01.2009"
        header_text = a.get_text(strip=True)
        nr_match = re.search(r"Nr\.\s*([\d/]+)", header_text)
        date_match = re.search(r"vom\s+(\d{2}\.\d{2}\.\d{4})", header_text)
        dok_nr = nr_match.group(1) if nr_match else ""
        datum = date_match.group(1) if date_match else ""
        pdf_url = a["href"]

        # Type and party are in the <p> immediately after <h4>
        # Format: "{DokTyp} {Party}" — party names can be multi-word
        PARTIES = [
            "BÜNDNIS 90/DIE GRÜNEN", "FREIE WÄHLER", "DIE LINKE",
            "CSU", "SPD", "AfD", "FDP", "FW", "Staatsregierung",
        ]
        typ_p = h4.find_next_sibling("p")
        if typ_p:
            typ_text = typ_p.get_text(strip=True)
            partei = next((p for p in PARTIES if typ_text.endswith(p)), "")
            dok_typ = typ_text[: len(typ_text) - len(partei)].strip() if partei else typ_text
        else:
            dok_typ, partei = "", ""

        # Title in <h5>
        h5 = h4.find_next_sibling("h5")
        titel = h5.get_text(strip=True) if h5 else ""

        # Keywords (Schlagworte) — appear as links after h5
        keywords = []
        if h5:
            for sib in h5.find_next_siblings():
                if sib.name == "h4":
                    break
                if "Schlagworte" in sib.get_text():
                    keywords = [a.get_text(strip=True) for a in sib.find_all("a")]

        records.append({
            "wahlperiode": wp,
            "dok_nr": dok_nr,
            "dok_typ": dok_typ.strip(),
            "partei": partei.strip(),
            "datum": datum,
            "titel": titel,
            "keywords": "; ".join(keywords),
            "pdf_url": pdf_url,
        })

    return records


def scrape_wp(wp: int) -> list[dict]:
    print(f"\nWP {wp}")
    params = {**BASE_PARAMS, "wahlperiodeid[]": str(wp), "page": 1}

    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    total_pages = get_total_pages(soup)
    print(f"  {total_pages} pages to scrape")

    all_records = parse_page(soup, wp)
    time.sleep(DELAY)

    for page in range(2, total_pages + 1):
        if page % 50 == 0:
            print(f"  page {page}/{total_pages} ({len(all_records)} records so far)")
        params = {**BASE_PARAMS, "wahlperiodeid[]": str(wp), "page": page}
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        all_records.extend(parse_page(soup, wp))
        time.sleep(DELAY)

    print(f"  → {len(all_records)} documents (WP {wp})")
    return all_records


def main():
    all_records = []
    for wp in WAHLPERIODEN:
        all_records.extend(scrape_wp(wp))

    df = pd.DataFrame(all_records)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"\nSaved {len(df)} records to {OUT_PATH}")


if __name__ == "__main__":
    main()
