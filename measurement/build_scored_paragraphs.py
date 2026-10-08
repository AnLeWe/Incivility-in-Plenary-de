"""One state's paragraphs with the LLM impoliteness and morality scores and the predicted TOPs.

Reads the full-corpus outputs of score_with_model.py for one state/model/variant, all paragraphs of
the protocols they come from (stateparl_v3_paragraphs.parquet, all affiliations, scored or not) and
the TOP side table of build_top_segments.py, and writes

  DATA_ROOT/processed/scored_paragraphs_<state>_<model>_<variant>.parquet
    all stateparl_v3_paragraphs columns, plus
    segment_idx       -1 = whole paragraph; 0, 1, ... = part of an nsc paragraph as split by
                      nsc_rule_parser.py (one row per scored part); empty = not scored
    nsc_type          type of that part (nsc.parquet)
    segment_text      the text the model saw (the paragraph, or the nsc part)
    impolite, impolite_reason, moral_civility, moral_reason
    top_id, top_seq, opener_score, is_opener_pred   (from top_segments_since_<date>.parquet)
    top_start         True on the first row of each TOP found by the opener model (top_seq >= 1)
  DATA_ROOT/processed/scored_paragraphs_<state>_<model>_<variant>.json   inputs, counts, run date

Rows are ordered by state, date, protocol_id, protocol_position, segment_idx.

Usage: norm_env/bin/python measurement/build_scored_paragraphs.py --state sn --model gemma4-12b --variant baseline
"""
import argparse, json, sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "preprocessing"))
from nsc_rule_parser import get_data_root

KEY = ["paragraph_id", "segment_idx"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="sn")
    parser.add_argument("--model", default="gemma4-12b")
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--tops-since", default="2009-09-29")
    args = parser.parse_args()
    root = get_data_root()
    tag = f"{args.state}_{args.model}_{args.variant}"
    inputs = {
        "impoliteness": root / "measurement" / f"impoliteness_full_{tag}.csv",
        "morality": root / "measurement" / f"morality_full_{tag}.csv",
        "paragraphs": root / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet",
        "nsc": root / "processed" / "nsc.parquet",
        "tops": root / "processed" / f"top_segments_since_{args.tops_since}.parquet",
    }

    imp = (pd.read_csv(inputs["impoliteness"], usecols=KEY + ["content", "impolite", "reason"])
             .rename(columns={"content": "segment_text", "reason": "impolite_reason"}))
    mor = (pd.read_csv(inputs["morality"], usecols=KEY + ["moral_civility", "reason"])
             .rename(columns={"reason": "moral_reason"}))
    scores = imp.merge(mor, on=KEY, how="outer", validate="one_to_one", indicator=True)
    assert (scores.pop("_merge") == "both").all(), "impoliteness and morality were scored on different rows"
    nsc = pd.read_parquet(inputs["nsc"], columns=KEY + ["nsc_type"]).drop_duplicates(KEY)
    scores = scores.merge(nsc, on=KEY, how="left", validate="one_to_one")

    raw = pd.read_parquet(inputs["paragraphs"])
    protocols = raw.loc[raw["paragraph_id"].isin(scores["paragraph_id"]), "protocol_id"].unique()
    raw = raw[raw["protocol_id"].isin(protocols)]
    out = raw.merge(scores, on="paragraph_id", how="left", validate="one_to_many")
    assert out["impolite"].notna().sum() == len(scores), "some scored paragraphs are missing from the raw file"

    tops = pd.read_parquet(inputs["tops"], columns=["paragraph_id", "top_id", "top_seq", "opener_score", "is_opener_pred"])
    out = out.merge(tops, on="paragraph_id", how="left", validate="many_to_one")

    out = out.sort_values(["state", "date", "protocol_id", "protocol_position", "segment_idx"]).reset_index(drop=True)
    out["top_start"] = ~out.duplicated("top_id") & (out["top_seq"] >= 1)
    out["impolite"] = out["impolite"].astype("boolean")
    out["segment_idx"] = out["segment_idx"].astype("Int64")

    stem = f"scored_paragraphs_{tag}"
    out.to_parquet(root / "processed" / f"{stem}.parquet", index=False)
    meta = {
        "run_date": date.today().isoformat(),
        "inputs": {k: str(v.relative_to(root)) for k, v in inputs.items()},
        "n_rows": len(out),
        "n_paragraphs": int(out["paragraph_id"].nunique()),
        "n_scored_rows": len(scores),
        "n_protocols": len(protocols),
        "n_tops": int(out["top_id"].nunique()),
        "n_rows_without_top": int(out["top_id"].isna().sum()),
        "impolite": {str(k): int(v) for k, v in out["impolite"].value_counts().items()},
        "moral_civility": out["moral_civility"].value_counts().to_dict(),
    }
    (root / "processed" / f"{stem}.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(meta, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
