"""TOP segments for every paragraph of the corpus, from the scored chair blocks.

Reads the block-level output of score_corpus.py and all paragraphs of
stateparl_v3_paragraphs.parquet from the same date on (all affiliations), and writes a side table
joinable by paragraph_id (the raw paragraphs file stays untouched):

  DATA_ROOT/processed/top_segments_since_<date>.parquet
    paragraph_id, protocol_id, protocol_position,
    block_id, opener_score, is_opener_pred   (pre paragraphs only, else empty)
    top_seq   number of predicted opener blocks up to and including this position in the
              protocol; 0 = before the protocol's first opener
    top_id    protocol_id + "_" + top_seq

A TOP starts at the first paragraph of its opener block and runs until the next opener block, so
speeches and interjections between two openers belong to the earlier one.

It also writes one document per TOP for topic modelling:

  DATA_ROOT/processed/tops_since_<date>.parquet
    top_id, protocol_id, state, period, date, top_seq, text, n_words
    text = the opener block (agenda heading) followed by the TOP's speech paragraphs (affiliation
    not pre and not nsc), in protocol order. Other chair rows and interjections are left out.
    Segment 0 (before the first opener) has no opener block, only speeches.

Usage: norm_env/bin/python measurement/top_change/build_top_segments.py --model g0_block_cv_pool --since 2009-09-29
"""
import argparse, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "preprocessing"))
from nsc_rule_parser import get_data_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="g0_block_cv_pool")
    parser.add_argument("--since", default="2009-09-29")
    args = parser.parse_args()
    root = get_data_root()
    blocks = pd.read_parquet(root / "measurement" / "top_change" / f"top_openers_{args.model}_since_{args.since}.parquet",
                             columns=["block_id", "protocol_id", "start_pos", "paragraph_ids", "score", "is_opener_pred"])
    raw = pd.read_parquet(root / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet",
                          columns=["paragraph_id", "protocol_id", "state", "period", "date", "protocol_position",
                                   "affiliation", "content"])
    raw = raw[pd.to_datetime(raw["date"]) >= pd.Timestamp(args.since)]
    rows = raw[["paragraph_id", "protocol_id", "protocol_position"]]
    rows = rows.sort_values(["protocol_id", "protocol_position"]).reset_index(drop=True)

    # block columns for the pre paragraphs
    pre = blocks.explode("paragraph_ids").rename(columns={"paragraph_ids": "paragraph_id", "score": "opener_score"})
    pre = pre[["paragraph_id", "block_id", "opener_score", "is_opener_pred"]]
    assert pre["paragraph_id"].is_unique
    out = rows.merge(pre, on="paragraph_id", how="left", validate="one_to_one")
    assert out["block_id"].notna().sum() == len(pre), "some scored paragraphs are missing from the raw file"

    # top_seq: opener block starts at or before each position, per protocol
    starts = blocks.loc[blocks["is_opener_pred"] == 1, ["protocol_id", "start_pos"]]
    codes = {pid: k for k, pid in enumerate(out["protocol_id"].unique())}
    span = int(out["protocol_position"].max()) + 1
    start_keys = np.sort(starts["protocol_id"].map(codes).to_numpy() * span + starts["start_pos"].to_numpy())
    row_keys = out["protocol_id"].map(codes).to_numpy() * span + out["protocol_position"].to_numpy()
    protocol_first = out["protocol_id"].map(codes).to_numpy() * span
    out["top_seq"] = np.searchsorted(start_keys, row_keys, side="right") - np.searchsorted(start_keys, protocol_first, side="left")
    out["top_id"] = out["protocol_id"] + "_" + out["top_seq"].astype(str)

    # each opener block has to start a new top_seq exactly at its first paragraph
    first_rows = out[out["block_id"].isin(blocks.loc[blocks["is_opener_pred"] == 1, "block_id"])].groupby("block_id")["top_seq"].agg(["min", "max"])
    assert (first_rows["min"] == first_rows["max"]).all()
    assert out.groupby("protocol_id")["top_seq"].max().sum() == int(blocks["is_opener_pred"].sum())

    path = root / "processed" / f"top_segments_since_{args.since}.parquet"
    out.to_parquet(path, index=False)
    print(f"wrote {path}: {len(out):,} paragraphs in {out['protocol_id'].nunique():,} protocols, "
          f"{out['top_id'].nunique():,} TOP segments ({int((out['top_seq'] > 0).groupby(out['top_id']).first().sum()):,} after an opener)")

    # TOP documents: opener block + speech paragraphs, in protocol order
    doc = out.merge(raw[["paragraph_id", "state", "period", "date", "affiliation", "content"]], on="paragraph_id")
    keep = (doc["is_opener_pred"] == 1) | ~doc["affiliation"].isin(["pre", "nsc"])
    doc = doc[keep]
    tops = doc.groupby("top_id", sort=False).agg(
        protocol_id=("protocol_id", "first"), state=("state", "first"), period=("period", "first"),
        date=("date", "first"), top_seq=("top_seq", "first"), text=("content", "\n".join)).reset_index()
    # TOPs with neither an opener block nor speech (segment 0 without speech) have no document
    tops["n_words"] = tops["text"].str.split().str.len()
    path = root / "processed" / f"tops_since_{args.since}.parquet"
    tops.to_parquet(path, index=False)
    print(f"wrote {path}: {len(tops):,} TOP documents, median {int(tops['n_words'].median()):,} words, "
          f"{(tops['n_words'] < 50).sum():,} under 50, {(tops['n_words'] < 100).sum():,} under 100, "
          f"longest {tops['text'].str.len().max():,} characters")


if __name__ == "__main__":
    main()
