"""
Download parliamentary motions and meta-text from the Brandenburg Landtag.

Source: Parlamentsdokumentation Brandenburg bulk XML exports
  https://www.parlamentsdokumentation.brandenburg.de/opendata/exportWP{n}.xml

Each XML file covers one Wahlperiode and contains metadata + PDF links for all
Drucksachen (Anträge, Anfragen, Plenarprotokolle, etc.).

WP 6 (2014–2019): AfD enters Brandenburg Landtag — treatment period starts here
WP 7 (2019–2024): continuation
WP 8 (2024–):     ongoing, file updated daily

Output (under DATA_ROOT/raw/):
  bb_motions_metadata.csv   — one row per document
  bb_motions_pdfs/          — downloaded PDFs (optional, see DOWNLOAD_PDFS)
"""

import os
import requests
import pandas as pd
import defusedxml.ElementTree as ET
from pathlib import Path
from tqdm import tqdm

BASE_URL = "https://www.parlamentsdokumentation.brandenburg.de/opendata/exportWP{wp}.xml"
PDF_BASE = "https://www.parlamentsdokumentation.brandenburg.de"

WAHLPERIODEN = [5, 6, 7, 8]

# Vorgang types to keep (VTyp field); covers motions, inquiries, and debate meta-text
KEEP_VTYPES = {"Antrag", "Anfrage", "Debatte", "Gesetz"}

DOWNLOAD_PDFS = False  # set True to also download PDF files

OUT_DIR = Path(os.environ["DATA_ROOT"]) / "raw"
PDF_DIR = OUT_DIR / "bb_motions_pdfs"


def fetch_xml(wp: int) -> ET.Element:
    url = BASE_URL.format(wp=wp)
    print(f"Fetching WP {wp}: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


def parse_documents(root: ET.Element, wp: int) -> list[dict]:
    records = []

    for vorgang in root:
        if vorgang.findtext("VFunktion") == "delete":
            continue

        vtyp = (vorgang.findtext("VTyp") or "").strip()
        if vtyp not in KEEP_VTYPES:
            continue

        keywords = "; ".join(
            n.findtext("Desk", "") for n in vorgang.findall("Nebeneintrag")
        )

        # Primary Drucksache document (DokArt == 'Drs')
        primary = next(
            (d for d in vorgang.findall("Dokument") if d.findtext("DokArt") == "Drs"),
            None,
        )
        # All PDF URLs across all linked documents
        all_urls = [u.text for d in vorgang.findall("Dokument") for u in d.findall("LokURL") if u.text and u.text.endswith(".pdf")]

        if primary is not None:
            dok_nr   = primary.findtext("DokNr", "")
            dok_dat  = primary.findtext("DokDat", "")
            titel    = primary.findtext("Titel", "")
            urheber  = primary.findtext("Urheber", "")
            dok_typ  = primary.findtext("DokTypL", "")
            pdf_url  = next((u.text for u in primary.findall("LokURL") if u.text and u.text.endswith(".pdf")), "")
            fund_st  = primary.findtext("FundSt", "")
        else:
            dok_nr = dok_dat = titel = urheber = dok_typ = pdf_url = fund_st = ""

        records.append({
            "wahlperiode":   wp,
            "vorgang_id":    vorgang.findtext("VNr", ""),
            "vtyp":          vtyp,
            "dok_nr":        dok_nr,
            "dok_typ":       dok_typ,
            "datum":         dok_dat,
            "titel":         titel,
            "urheber":       urheber,
            "keywords":      keywords,
            "fundstelle":    fund_st,
            "pdf_url":       pdf_url,
            "all_pdf_urls":  " | ".join(all_urls),
        })

    return records


def download_pdf(url: str, dest: Path) -> None:
    if dest.exists():
        return
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    except Exception as e:
        print(f"  Warning: could not download {url}: {e}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if DOWNLOAD_PDFS:
        PDF_DIR.mkdir(parents=True, exist_ok=True)

    all_records = []

    for wp in WAHLPERIODEN:
        root = fetch_xml(wp)
        records = parse_documents(root, wp)
        all_records.extend(records)
        print(f"  → {len(records)} documents kept (WP {wp})")

    df = pd.DataFrame(all_records)
    out_path = OUT_DIR / "bb_motions_metadata.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"\nSaved {len(df)} records to {out_path}")

    if DOWNLOAD_PDFS:
        print(f"\nDownloading PDFs to {PDF_DIR} ...")
        for _, row in tqdm(df.iterrows(), total=len(df)):
            if not row["pdf_url"]:
                continue
            fname = row["pdf_url"].split("/")[-1] or f"{row['dok_nr']}.pdf"
            download_pdf(row["pdf_url"], PDF_DIR / fname)


if __name__ == "__main__":
    main()
