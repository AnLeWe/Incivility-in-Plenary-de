"""
Derive each state's AfD entry (and, where applicable, exit) date directly from
the corpus, as a small cached table other scripts (Python or R) can just read
and merge — instead of each re-deriving it independently.

Method: a (state, period) counts as "AfD present" if any row in it has
affiliation == "afd"; interval bounds are the period's own first/last sitting
date (not the first/last afd-affiliated row's date) — verified against the
full corpus: the gap between a period's constitutive session and its first
afd-affiliated row is 0 days for 10/16 states, at most 29 days for the rest
(mv, sl). A state's entry date is the first such period's start date. A state
counts as having exited only if its most recent period overall has no AfD
row; in that case exit_date is the end date of the last period that did have
one. Two states currently exited this way: Bremen (hb, seats in periods 19-20,
none in 21) and Schleswig-Holstein (sh, seats in period 19, none in 20)
— all other states still hold AfD seats in their latest period, so
exit_date is null for them.

This is the same method (and produces identical entry dates, plus the same
exit dates for hb/sh) as `AFD_PRESENCE` in analysis/nsc_analysis.ipynb, which
additionally tracks the full interval history (relevant if a state ever
exits and later re-enters); this script only needs the current entry/exit
state, not the full history.

Output: DATA_ROOT/processed/afd_entry_dates.csv
  Columns: state, entry_date, exit_date (16 rows, one per state;
  exit_date is empty/NaT for states that still hold AfD seats).

Usage:
    norm_env/bin/python src/afd_entry_dates.py
"""
import os
from pathlib import Path

import pandas as pd


def get_data_root() -> Path:
    data_root = os.environ.get("DATA_ROOT")
    if not data_root:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv())
        data_root = os.environ.get("DATA_ROOT")
    if not data_root:
        raise SystemExit("DATA_ROOT not set. Copy .env.example to .env and set DATA_ROOT.")
    return Path(data_root)


def derive_afd_entry_dates(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """Derive entry/exit dates per state from a paragraphs DataFrame with
    columns state, period, date, affiliation. Returns a DataFrame with
    columns state, entry_date, exit_date, one row per state that has any
    afd row. exit_date is NaT unless the state's most recent period overall
    has no afd row (i.e. AfD held seats at some point but not currently)."""
    period_bounds = (
        paragraphs.groupby(["state", "period"])["date"]
        .agg(period_start="min", period_end="max")
    )
    afd_periods = set(
        paragraphs.loc[paragraphs["affiliation"] == "afd", ["state", "period"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )

    rows = []
    for state, group in period_bounds.groupby(level="state"):
        group = group.droplevel("state").sort_index()
        afd_group = group[[(state, period) in afd_periods for period in group.index]]
        if afd_group.empty:
            continue
        last_period_overall = group.index.max()
        currently_present = (state, last_period_overall) in afd_periods
        rows.append({
            "state": state,
            "entry_date": afd_group["period_start"].iloc[0],
            "exit_date": pd.NaT if currently_present else afd_group["period_end"].iloc[-1],
        })

    return pd.DataFrame(rows)


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
