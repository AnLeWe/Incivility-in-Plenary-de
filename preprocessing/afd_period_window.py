"""Builds the shared pre/post-AfD-entry speech dataset used by any pipeline that needs
speeches scoped to a state's legislative period immediately before vs. immediately after
AfD entry (currently: measurement/topic_modeling_lib.py). See
docs/superpowers/specs/2026-08-14-topic-modeling-lda-design.md (local-only) for rationale.
"""
import os

import pandas as pd

NON_SPEECH_AFFILIATION = "nsc"


def derive_period_windows(protocols: pd.DataFrame, afd_entry: pd.DataFrame) -> dict[str, dict[str, int]]:
    """For each state in `afd_entry`, find the legislative period that starts at/after the
    state's AfD entry date (`post`) and the period immediately before it (`pre`).

    States with no prior period available (the first known period is already `post`) or not
    present in `afd_entry` are omitted from the result.
    """
    period_starts = (
        protocols.groupby(["state", "period"])["date"].min().reset_index()
    )
    entry_by_state = afd_entry.set_index("state")["entry_date"]

    windows: dict[str, dict[str, int]] = {}
    for state, group in period_starts.groupby("state"):
        if state not in entry_by_state.index:
            continue
        entry_date = entry_by_state[state]
        group = group.sort_values("period").reset_index(drop=True)

        post_candidates = group[group["date"] >= entry_date]
        if post_candidates.empty:
            continue
        post_period = int(post_candidates.iloc[0]["period"])
        post_idx = group.index[group["period"] == post_period][0]
        if post_idx == 0:
            continue

        pre_period = int(group.iloc[post_idx - 1]["period"])
        windows[state] = {"pre": pre_period, "post": post_period}

    return windows


def build_speech_documents(paragraphs: pd.DataFrame, period_windows: dict[str, dict[str, int]]) -> pd.DataFrame:
    """One row per speech falling inside its state's pre- or post-AfD-entry period, with
    paragraph content concatenated in reading order. Excludes `nsc` (interjection) rows --
    those interrupt a speech, they aren't part of it."""
    keep_mask = pd.Series(False, index=paragraphs.index)
    pre_post_lookup: dict[tuple[str, int], str] = {}
    for state, window in period_windows.items():
        for label, period in window.items():
            in_window = (paragraphs["state"] == state) & (paragraphs["period"] == period)
            keep_mask |= in_window
            pre_post_lookup[(state, period)] = label

    scoped = paragraphs[keep_mask & (paragraphs["affiliation"] != NON_SPEECH_AFFILIATION)].copy()
    scoped = scoped.sort_values(["speech_id", "protocol_position", "segment_position"])

    grouped = scoped.groupby("speech_id").agg(
        state=("state", "first"),
        period=("period", "first"),
        date=("date", "first"),
        text=("content", lambda s: " ".join(s.dropna())),
    ).reset_index()

    grouped["pre_post"] = [
        pre_post_lookup[(row.state, row.period)] for row in grouped.itertuples()
    ]

    return grouped[["speech_id", "state", "period", "pre_post", "date", "text"]]


def main(data_root: str) -> None:
    raw = os.path.join(data_root, "raw")
    proc = os.path.join(data_root, "processed")
    v3 = os.path.join(raw, "stateparl_v3_parquet")

    protocols = pd.read_parquet(os.path.join(v3, "stateparl_v3_protocols.parquet"))
    protocols["date"] = pd.to_datetime(protocols["date"])

    afd_entry = pd.read_csv(os.path.join(proc, "afd_entry_dates.csv"), parse_dates=["entry_date"])

    paragraphs = pd.read_parquet(os.path.join(v3, "stateparl_v3_paragraphs.parquet"))
    paragraphs["date"] = pd.to_datetime(paragraphs["date"])

    windows = derive_period_windows(protocols, afd_entry)
    print(f"Derived pre/post periods for {len(windows)} of {afd_entry['state'].nunique()} states")

    docs = build_speech_documents(paragraphs, windows)
    print(f"Built {len(docs):,} speech documents across {docs['state'].nunique()} states")

    out_path = os.path.join(proc, "speeches_afd_prepost.parquet")
    docs.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main(os.environ["DATA_ROOT"])
