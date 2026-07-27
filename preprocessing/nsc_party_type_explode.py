"""
Explode nsc.parquet into one row per (nsc_type, party) — the atomic unit the
aggregate/crosstab/time-series analysis in analysis/nsc_analysis.ipynb needs. A single
parsed segment can carry:
  - multiple co-occurring reaction types, pipe-joined ("Heiterkeit|Beifall")
  - multiple attributed parties, pipe-joined ("CDU|SPD")
Both get split into separate rows here so every row has at most one type and at
most one party.

**Not used for LLM impoliteness classification** (renamed from nsc_llm_explode.py
2026-07-27 to reflect this — see
docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md). Classification reads
nsc.parquet directly instead: exploding on party here means the same span of text (e.g.
"Beifall bei der SPD und der CDU") becomes multiple rows with identical content_text,
which would get double-labeled by an LLM. This explosion is only correct for counting
each party's/type's share of events, not for text classification.

Segments with neither multiplicity pass through unchanged — the large majority:
per nsc_rule_parser.py diagnostics, only ~1.1% of interjection segments are
multi-type and ~19% multi-party.

Segments with BOTH multi-type and multi-party (~0.45%) are split independently on
each dimension in sequence (explode nsc_type, then explode party_canonical), which
naturally produces the full type x party cross-product — e.g. "Heiterkeit|Beifall"
x "SPD|GRÜNE" -> 4 rows. This is a deliberate simplification, not an oversight: the
source text usually doesn't say which specific type paired with which specific
party ("Heiterkeit und Beifall bei der SPD und den GRÜNEN" doesn't say who laughed
vs. who applauded), so cross-product is the only non-arbitrary way to make every
row atomic. Order of the two explodes doesn't affect the result — it's two
independent splits, not special-cased pairing logic.

Rows with no party and no named speaker (~6% of interjections) are kept as one row
with an empty party_canonical — the reaction-type signal (Beifall, Unruhe, ...) is
still real and classifiable even unattributed.

Non-interjection row types (glocke, Prozedural, misattributed, document_reference,
garbled — see nsc_rule_parser.NON_INTERJECTION_TYPES) are excluded. Note: the
capitalized "Glocke" nsc_type value (a chair's-bell reaction tag on an otherwise-real
interjection row, distinct from the lowercase row-type-level "glocke") is deliberately
*not* in that exclusion set and is *kept* here — checked empirically, Glocke segments
co-occur with Unruhe far above baseline rate, indicating the chair intervening in
response to disorder, a real signal close to the Ordnungsruf variable planned in
CLAUDE.md. Do not add "Glocke" to the exclusion set.

affiliation_derived is recomputed per exploded party — the nsc.parquet column
reflects the FULL pre-split party_canonical (or, for a named speaker, their role),
not any single one of its post-split parts.

Output: DATA_ROOT/processed/nsc_party_type.parquet
  One row per (source segment) x (type) x (party) combination.
  New columns vs. nsc.parquet:
    orig_n_types   — how many pipe-joined types the source segment had (>=1)
    orig_n_parties — how many pipe-joined parties the source segment had (0 = none)

Usage:
    norm_env/bin/python preprocessing/nsc_party_type_explode.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nsc_rule_parser import get_data_root, _derive_affiliation, NON_INTERJECTION_TYPES


def explode_for_llm(nsc_df: pd.DataFrame) -> pd.DataFrame:
    """Take a parsed nsc segment-level DataFrame and return one row per
    (nsc_type, party_canonical) atomic unit. See module docstring for the design
    rationale (sequential independent explode, cross-product for the rare overlap,
    blank-party rows preserved, non-interjection rows excluded, Glocke retained)."""
    df = nsc_df[~nsc_df["nsc_type"].isin(NON_INTERJECTION_TYPES)].copy()

    df["orig_n_types"] = df["nsc_type"].str.split("|").apply(len)
    df["orig_n_parties"] = df["party_canonical"].apply(
        lambda p: len(p.split("|")) if p else 0
    )

    df = df.assign(nsc_type=df["nsc_type"].str.split("|")).explode("nsc_type")
    df = df.assign(
        party_canonical=df["party_canonical"].apply(lambda p: p.split("|") if p else [""])
    ).explode("party_canonical")

    df["affiliation_derived"] = [
        _derive_affiliation(role, party)
        for role, party in zip(df["role"], df["party_canonical"])
    ]

    return df.reset_index(drop=True)


def main() -> None:
    data_root = get_data_root()
    src = data_root / "processed" / "nsc.parquet"
    out = data_root / "processed" / "nsc_party_type.parquet"

    print(f"Reading {src} ...")
    nsc_df = pd.read_parquet(src)
    n_interjection = (~nsc_df["nsc_type"].isin(NON_INTERJECTION_TYPES)).sum()
    print(f"  {len(nsc_df):,} segments  ({n_interjection:,} interjections)")

    print("Exploding ...")
    exploded = explode_for_llm(nsc_df)

    print(f"\nOutput: {len(exploded):,} rows  ({len(exploded)/n_interjection:.2f}x interjection segments)")
    print(f"Rows from a multi-type source segment:   {(exploded['orig_n_types'] > 1).sum():,}")
    print(f"Rows from a multi-party source segment:  {(exploded['orig_n_parties'] > 1).sum():,}")
    print(f"Rows with empty party_canonical:         {(exploded['party_canonical'] == '').sum():,}")

    exploded.to_parquet(out, index=False)
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
