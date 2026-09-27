"""Pairwise + joint inter-rater agreement across the models scored on the fixed pilot sample.

Usage: norm_env/bin/python compute_interrater_agreement.py

Finds every impoliteness_pilot_predictions_*_n2000.csv in DATA_ROOT/measurement/, pivots to
one impolite/not-impolite column per model, and reports:
- pairwise raw percent agreement + Cohen's kappa (chance-corrected, binary, exactly 2 raters)
- Fleiss' kappa across all raters jointly (3+ raters, nominal, needs complete data -- every
  unit rated by the same number of raters)
- Krippendorff's alpha across all raters jointly (any number of raters, any measurement
  level, handles missing ratings natively rather than requiring them dropped -- the standard
  reliability statistic in political-science/content-analysis methodology specifically, so
  reported as the primary joint number; Fleiss' kappa is kept alongside as a cross-check --
  the two matched to 3 decimal places on the 2026-07-28 4-model run, which is expected since
  they're closely related for complete nominal data).

Cohen's/Fleiss' kappa implemented directly (no sklearn/statsmodels dependency, a few lines
each for the binary case). Krippendorff's alpha uses the `krippendorff` package instead of a
hand-rolled implementation -- the coincidence-matrix math has enough subtlety (see e.g. the
small-sample correction) that a well-tested dedicated package is safer than reinventing it for
a number that'll end up reported in the thesis.
"""
import argparse
import glob
import os
from pathlib import Path

import krippendorff
import numpy as np
import pandas as pd


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's kappa for two boolean rating arrays of equal length."""
    n = len(a)
    po = (a == b).mean()
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def fleiss_kappa(ratings: np.ndarray) -> float:
    """Fleiss' kappa for a (subjects x categories) count matrix, binary categories.

    `ratings` here is (n_subjects, 2): count of "impolite" / "not impolite" votes per row.
    """
    n_subjects, n_categories = ratings.shape
    n_raters = ratings.sum(axis=1)[0]  # assumed constant across subjects
    p_i = ((ratings ** 2).sum(axis=1) - n_raters) / (n_raters * (n_raters - 1))
    p_bar = p_i.mean()
    p_j = ratings.sum(axis=0) / (n_subjects * n_raters)
    pe_bar = (p_j ** 2).sum()
    return (p_bar - pe_bar) / (1 - pe_bar) if pe_bar != 1 else float("nan")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500, help="Sample size to match on (n500, n2000, ...)")
    args = parser.parse_args()

    data_root = os.environ.get("DATA_ROOT")
    if not data_root:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv())
        data_root = os.environ["DATA_ROOT"]

    pattern = str(Path(data_root) / "measurement" / f"impoliteness_pilot_predictions_*_n{args.n}.csv")
    paths = sorted(glob.glob(pattern))
    if not paths:
        print(f"No prediction files found matching {pattern}")
        return

    wide = None
    model_names = []
    for path in paths:
        df = pd.read_csv(path)
        model = df["model_name"].iloc[0]
        model_names.append(model)
        col = df[["paragraph_id", "impolite"]].rename(columns={"impolite": model})
        wide = col if wide is None else wide.merge(col, on="paragraph_id", how="outer")
        print(f"Loaded {path} -> model={model}, {len(df):,} rows")

    print(f"\n{len(model_names)} models, {len(wide):,} distinct paragraphs across all files")

    complete = wide.dropna(subset=model_names)
    n_dropped = len(wide) - len(complete)
    if n_dropped:
        print(f"{n_dropped} paragraphs missing a prediction from >=1 model (unparseable "
              f"response, or not in that model's sample) -- excluded from pairwise/Fleiss' "
              f"kappa below (both need complete data), kept as missing (not dropped) for "
              f"Krippendorff's alpha")

    print("\n-- Pairwise agreement --")
    for i, m1 in enumerate(model_names):
        for m2 in model_names[i + 1:]:
            a = complete[m1].astype(bool).to_numpy()
            b = complete[m2].astype(bool).to_numpy()
            raw_agree = (a == b).mean()
            kappa = cohen_kappa(a, b)
            print(f"  {m1} vs {m2}: raw agreement = {raw_agree:.1%}, Cohen's kappa = {kappa:.3f}")

    print(f"\n-- Joint agreement across all {len(model_names)} raters --")

    if len(model_names) >= 3:
        votes = complete[model_names].astype(bool).to_numpy()
        counts = np.stack([(~votes).sum(axis=1), votes.sum(axis=1)], axis=1)  # [not-impolite, impolite]
        fk = fleiss_kappa(counts)
        print(f"Fleiss' kappa (complete-data subset, n={len(complete):,}) = {fk:.3f}")

    # (raters x units) matrix, NaN preserved for missing -- Krippendorff's alpha handles this
    # natively, unlike Cohen's/Fleiss' kappa above which both need the dropna'd subset.
    reliability_data = wide[model_names].to_numpy(dtype=float).T
    alpha = krippendorff.alpha(reliability_data=reliability_data, level_of_measurement="nominal")
    print(f"Krippendorff's alpha (nominal, n={len(wide):,}, missing kept as missing) = {alpha:.3f}")


if __name__ == "__main__":
    main()
