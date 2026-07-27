"""
Build a paragraph-level side table flagging which paragraphs are nsc-affiliated
(is_nsc) and, for those, a proper party attribution (affiliation_derived) — instead
of the uninformative raw affiliation == "nsc" code. Joinable onto
stateparl_v3_paragraphs.parquet by paragraph_id. paragraphs.parquet itself is the
externally-sourced StateParl release and is not modified in place — see
docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md, Decision 3.

Granularity: one row per paragraph_id, matching paragraphs.parquet's own grain — not
one row per nsc.parquet segment. For multi-segment paragraphs, affiliation_derived is
taken from segment_idx == 0 (the first segment) as a representative value; the full
per-segment detail (multiple types/parties per paragraph) remains available in
nsc.parquet itself for consumers that need it (e.g. the classification path).

is_nsc is True for every paragraph_id present in nsc.parquet — this includes rows
classified as document_reference/misattributed/Prozedural/garbled/glocke, not just
"real" interjection content, since it's meant to mirror
paragraphs.affiliation == "nsc" exactly (just as an explicit boolean flag rather than
requiring every consumer to re-check the raw affiliation string).

Output: DATA_ROOT/processed/nsc_paragraph_flags.parquet
  Columns: paragraph_id, is_nsc, affiliation_derived

Usage:
    norm_env/bin/python preprocessing/nsc_paragraph_flags.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nsc_rule_parser import get_data_root


def build_paragraph_flags(nsc_df: pd.DataFrame) -> pd.DataFrame:
    """One row per paragraph_id: is_nsc flag + first-segment affiliation_derived."""
    first_segment = (
        nsc_df.sort_values(["paragraph_id", "segment_idx"])
        .drop_duplicates("paragraph_id", keep="first")[["paragraph_id", "affiliation_derived"]]
    )
    first_segment["is_nsc"] = True
    return first_segment[["paragraph_id", "is_nsc", "affiliation_derived"]].reset_index(drop=True)


def main() -> None:
    data_root = get_data_root()
    src = data_root / "processed" / "nsc.parquet"
    out = data_root / "processed" / "nsc_paragraph_flags.parquet"

    print(f"Reading {src} ...")
    nsc_df = pd.read_parquet(src, columns=["paragraph_id", "segment_idx", "affiliation_derived"])

    flags = build_paragraph_flags(nsc_df)
    n_blank = (flags["affiliation_derived"] == "").sum()
    print(f"Built {len(flags):,} paragraph-level rows from "
          f"{nsc_df['paragraph_id'].nunique():,} distinct nsc paragraphs")
    print(f"Blank affiliation_derived: {n_blank:,} ({n_blank / len(flags) * 100:.1f}%)")

    flags.to_parquet(out, index=False)
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
