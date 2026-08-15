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
