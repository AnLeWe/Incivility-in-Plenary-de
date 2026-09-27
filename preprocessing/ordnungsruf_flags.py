"""
Build a paragraph-level flag: does an Ordnungsruf (formal chair sanction) get issued
later in the same protocol for this paragraph's speaker?

Not a proximity window -- checked empirically (see chat log 2026-07-29) that real
Ordnungsrufe are often issued well after the offending paragraph, sometimes after
unrelated agenda items, because the chair reviews the Wortprotokoll before deciding
(e.g. protocol bb_3_32: "Ich habe aber nicht sofort eingegriffen, sondern mir erst
das Wortprotokoll vorlegen lassen ... Meine erste Entscheidung betrifft den
Redebeitrag von Frau Fechner ... ich erteile Frau Fechner einen Ordnungsruf" --
15 paragraphs after her speech, referencing her by name, not by position). A fixed
±N-paragraph context window can't reliably capture this; matching by speaker name
against later chair paragraphs can.

Method: within each protocol, find affiliation=="pre" paragraphs containing
"Ordnungsruf" (3,872 across 1,670 of 9,492 protocols -- only these protocols need
checking). For every paragraph with a mandate_id, take the surname (mandate_id's
last "_"-separated token, e.g. "bb_3_dvu_fechner" -> "fechner") and flag it True if
that surname appears in a later same-protocol Ordnungsruf-paragraph.

Known limitation: surname-substring matching, not a mandate_id reference -- two
mandates sharing a surname in the same protocol would both get flagged. Rare (checked
against the Fechner/Ludwig examples in bb_3_32, both matched correctly), not corrected
for here.

Output: DATA_ROOT/processed/ordnungsruf_flags.parquet
  Columns: paragraph_id, ordnungsruf_follows

Usage:
    norm_env/bin/python preprocessing/ordnungsruf_flags.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nsc_rule_parser import get_data_root


def build_ordnungsruf_flags(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """paragraphs needs: paragraph_id, protocol_id, protocol_position, affiliation,
    mandate_id, content.

    Iterates per sanction paragraph (~3,872 total), not per input paragraph (~16M) --
    for each sanction, look up the (few dozen, per protocol) distinct surnames that
    appear earlier in the same protocol and test which are substrings of the
    sanction's text, then flag every matching paragraph in one vectorized pass.
    """
    is_ordnungsruf = (
        (paragraphs["affiliation"] == "pre")
        & paragraphs["content"].astype(str).str.contains("Ordnungsruf", case=False, na=False)
    )
    surname = paragraphs["mandate_id"].astype(str).str.rsplit("_", n=1).str[-1].str.lower()
    surname = surname.where(paragraphs["mandate_id"].notna() & (surname != "nan"), "")

    df = paragraphs[["paragraph_id", "protocol_id", "protocol_position"]].copy()
    df["surname"] = surname
    df["is_ordnungsruf"] = is_ordnungsruf.to_numpy()
    df["content_lower"] = paragraphs["content"].astype(str).str.lower()

    affected_protocols = df.loc[df["is_ordnungsruf"], "protocol_id"].unique()
    scoped = df[df["protocol_id"].isin(affected_protocols)]
    flags = pd.Series(False, index=df.index)

    for protocol_id, group in scoped.groupby("protocol_id"):
        sanctions = group[group["is_ordnungsruf"]]
        candidates = group[group["surname"] != ""]
        for _, sanction in sanctions.iterrows():
            earlier = candidates[candidates["protocol_position"] < sanction["protocol_position"]]
            if earlier.empty:
                continue
            matched = earlier[earlier["surname"].apply(lambda s: s in sanction["content_lower"])]
            flags.loc[matched.index] = True

    return pd.DataFrame({
        "paragraph_id": paragraphs["paragraph_id"],
        "ordnungsruf_follows": flags.to_numpy(),
    }).reset_index(drop=True)


def main() -> None:
    data_root = get_data_root()
    src = data_root / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet"
    out = data_root / "processed" / "ordnungsruf_flags.parquet"

    print(f"Reading {src} ...")
    paragraphs = pd.read_parquet(
        src, columns=["paragraph_id", "protocol_id", "protocol_position", "affiliation",
                      "mandate_id", "content"],
    )

    flags = build_ordnungsruf_flags(paragraphs)
    n_flagged = flags["ordnungsruf_follows"].sum()
    print(f"Built {len(flags):,} paragraph-level rows; {n_flagged:,} flagged "
          f"ordnungsruf_follows=True ({n_flagged / len(flags) * 100:.3f}%)")

    flags.to_parquet(out, index=False)
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
