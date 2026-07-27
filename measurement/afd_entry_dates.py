"""
Derive each state's AfD entry date directly from the corpus, as a small cached
table other scripts (Python or R) can just read and merge — instead of each
re-deriving it independently.

Method: a (state, period) counts as "AfD present" if any row in it has
affiliation == "afd"; the interval bound is the period's own first sitting
date (not the first afd-affiliated row's date) — verified against the full
corpus: the gap between a period's constitutive session and its first
afd-affiliated row is 0 days for 10/16 states, at most 29 days for the rest
(mv, sl). A state's entry date is the first such period's start date.

This is the same method (and produces identical dates) as `AFD_PRESENCE` in
analysis/nsc_analysis.ipynb, which additionally tracks exit/re-entry
intervals; this script only needs the first entry, not the full history.

Output: DATA_ROOT/processed/afd_entry_dates.csv
  Columns: state, entry_date (16 rows, one per state).

Usage:
    norm_env/bin/python measurement/afd_entry_dates.py
"""
import pandas as pd

from nsc_rule_parser import get_data_root


def derive_afd_entry_dates(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """Derive one entry date per state from a paragraphs DataFrame with
    columns state, period, date, affiliation. Returns a DataFrame with
    columns state, entry_date, one row per state that has any afd row."""
    period_bounds = (
        paragraphs.groupby(["state", "period"])["date"]
        .min()
        .rename("period_start")
    )

    entry = (
        paragraphs.loc[paragraphs["affiliation"] == "afd", ["state", "period"]]
        .drop_duplicates()
        .merge(period_bounds, on=["state", "period"])
        .sort_values(["state", "period"])
        .groupby("state")["period_start"]
        .first()
        .rename("entry_date")
        .reset_index()
    )
    return entry


def main() -> None:
    data_root = get_data_root()
    src = data_root / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet"
    out = data_root / "processed" / "afd_entry_dates.csv"

    print(f"Reading {src} ...")
    paragraphs = pd.read_parquet(src, columns=["state", "period", "date", "affiliation"])
    paragraphs["date"] = pd.to_datetime(paragraphs["date"])

    entry = derive_afd_entry_dates(paragraphs)
    print(f"States with an AfD entry date: {len(entry)} of {paragraphs['state'].nunique()}")
    print(entry.to_string(index=False))

    out.parent.mkdir(parents=True, exist_ok=True)
    entry.to_csv(out, index=False)
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
