"""Prompt construction and response parsing for the impoliteness pilot's zero-shot
LLM classifier. See docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md.

Personal-attack sub-criteria in SYSTEM_PROMPT operationalize Jacob et al. (2026, p.3),
who reached 92% accuracy against expert-coded gold labels with GPT-4o using this
definition.
"""
import json
import sys
from collections import namedtuple
from pathlib import Path

import pandas as pd

from prompts import PROMPT_VERSION, PROMPTS, SYSTEM_PROMPT


ClassificationPool = namedtuple(
    "ClassificationPool", ["paragraphs", "nsc", "afd_entry", "para_window", "merged", "dedup"]
)


def build_classification_pool(data_root, verbose: bool = True) -> ClassificationPool:
    """Build the pilot's ±1yr-AfD-window classification-ready pool.

    Single source of truth for this pipeline -- was duplicated between
    impoliteness_pilot.ipynb and analysis/data_exploration.ipynb, now both just call this.
    See docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md and
    2026-07-27-nsc-pipeline-cleanup-design.md for the full rationale behind each step.

    Returns every named intermediate (not just `dedup`) so callers that want to inspect a
    specific step (e.g. `pool.nsc.head()`, sanity-checking `pool.merged`) still can.
    """
    repo = Path(__file__).resolve().parent.parent
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from preprocessing.nsc_rule_parser import NON_INTERJECTION_TYPES

    raw = Path(data_root) / "raw"
    proc = Path(data_root) / "processed"
    v3 = raw / "stateparl_v3_parquet"

    paragraphs = pd.read_parquet(v3 / "stateparl_v3_paragraphs.parquet")
    paragraphs["date"] = pd.to_datetime(paragraphs["date"])

    nsc = pd.read_parquet(proc / "nsc.parquet")
    n_before = len(nsc)
    nsc = nsc[~nsc["nsc_type"].isin(NON_INTERJECTION_TYPES)].copy()
    if verbose:
        print(f"paragraphs: {paragraphs.shape[0]:,} rows, {paragraphs['state'].nunique()} states")
        print(f"nsc.parquet: {n_before:,} segments -> {len(nsc):,} after excluding "
              f"non-interjection row types")

    afd_entry = (pd.read_csv(proc / "afd_entry_dates.csv", parse_dates=["entry_date"])
                    .set_index("state")["entry_date"]
                    .dt.date
                    .to_dict())

    window = pd.DateOffset(years=1)
    entry_window = {s: (d - window, d + window) for s, d in afd_entry.items()}
    mask = pd.Series(False, index=paragraphs.index)
    for state, (start, end) in entry_window.items():
        mask |= (paragraphs["state"] == state) & paragraphs["date"].between(start, end)
    para_window = paragraphs[mask].copy()
    if verbose:
        print(f"para_window (+/-1yr around each state's AfD entry): {len(para_window):,} "
              f"of {len(paragraphs):,} paragraphs")

    redundant = ["protocol_id", "speech_id", "state", "period", "nth", "date",
                 "protocol_position", "raw_row"]
    nsc_slim = nsc.drop(columns=redundant)
    merged = para_window.merge(nsc_slim, on="paragraph_id", how="left")

    is_nsc_row = merged["affiliation"] == "nsc"
    merged["text_to_classify"] = merged["content"]
    merged.loc[is_nsc_row, "text_to_classify"] = merged.loc[is_nsc_row, "content_text"]

    classifiable = merged[
        ~is_nsc_row | (merged["text_to_classify"].notna() & (merged["text_to_classify"] != ""))
    ].copy()
    dedup = classifiable.drop_duplicates(subset=["paragraph_id", "segment_idx"], keep="first")

    ordnungsruf = pd.read_parquet(proc / "ordnungsruf_flags.parquet")
    dedup = dedup.merge(ordnungsruf, on="paragraph_id", how="left")
    dedup["ordnungsruf_follows"] = dedup["ordnungsruf_follows"].fillna(False)

    if verbose:
        print(f"merged: {len(merged):,} rows; classifiable+deduplicated: {len(dedup):,}")

    return ClassificationPool(paragraphs, nsc, afd_entry, para_window, merged, dedup)


def build_position_index(merged: pd.DataFrame) -> pd.DataFrame:
    """One representative row per (protocol_id, protocol_position) from `merged`, for
    ±1-paragraph context lookups -- collapses multi-segment nsc rows to their first
    segment (98.9% of interjection clusters are 1 paragraph anyway, see
    docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md)."""
    return (
        merged.sort_values(["protocol_id", "protocol_position", "segment_idx"])
        .drop_duplicates(subset=["protocol_id", "protocol_position"], keep="first")
        .set_index(["protocol_id", "protocol_position"])
    )


def _speaker_label(row) -> str:
    aff = row.get("affiliation_derived")
    if not (isinstance(aff, str) and aff):
        aff = row.get("affiliation")
    if aff == "pre":
        return "PRÄSIDIUM"
    return str(aff).upper() if isinstance(aff, str) and aff else "?"


def build_context(target_row, position_index: pd.DataFrame) -> dict:
    """±1-paragraph context for one target row (a `dedup` row) -- see build_prompt()."""
    protocol_id = target_row["protocol_id"]
    pos = target_row["protocol_position"]
    context = {
        "prev": None,
        "next": None,
        "ordnungsruf_follows": bool(target_row.get("ordnungsruf_follows", False)),
    }
    for offset, key in ((-1, "prev"), (1, "next")):
        loc = (protocol_id, pos + offset)
        if loc not in position_index.index:
            continue
        row = position_index.loc[[loc]].iloc[0]
        text = row.get("text_to_classify")
        if not (isinstance(text, str) and text):
            continue
        same_turn = (
            pd.notna(row.get("speech_id"))
            and pd.notna(target_row.get("speech_id"))
            and row.get("speech_id") == target_row.get("speech_id")
        )
        context[key] = {"label": _speaker_label(row), "text": text, "same_speaker_turn": bool(same_turn)}
    return context


def build_prompt(text: str, context: dict | None = None, prompt_version: str = PROMPT_VERSION) -> list[dict]:
    """Build the Ollama chat messages for classifying one paragraph.

    `prompt_version` selects which SYSTEM_PROMPT_* text from prompts.py to use (defaults to
    the current PROMPT_VERSION) -- e.g. score_with_model.py's "baseline" ablation variant
    passes the actual v1 version explicitly, so it uses v1's real text rather than whatever
    text happens to be current.

    `context` (optional, from build_context()) adds a ±1-paragraph window, each side
    labeled with speaker/role and whether it's the same speaking turn as the target, plus
    an explicit ordnungsruf_follows hint -- see the v2 prompt's "Eingabeformat" section for
    what the model is told about this structure. Without `context`, behaves as before
    (just the isolated paragraph text).
    """
    system_prompt = PROMPTS[prompt_version]

    if not context:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

    parts = []
    if context.get("prev"):
        p = context["prev"]
        turn = "gleiche Sprechperson" if p["same_speaker_turn"] else "andere Sprechperson"
        parts.append(f"[VORHERIGER ABSATZ – {p['label']}, {turn}]\n{p['text']}")
    parts.append(f"[ZU BEWERTENDER ABSATZ]\n{text}")
    if context.get("next"):
        n = context["next"]
        turn = "gleiche Sprechperson" if n["same_speaker_turn"] else "andere Sprechperson"
        parts.append(f"[NACHFOLGENDER ABSATZ – {n['label']}, {turn}]\n{n['text']}")
    if context.get("ordnungsruf_follows"):
        parts.append(
            "[HINWEIS: Für die Person des zu bewertenden Absatzes wird im weiteren "
            "Protokollverlauf ein Ordnungsruf erteilt.]"
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def parse_response(raw: str) -> dict:
    """Parse the model's raw text response into
    {"impolite": bool|None, "reason": str|None, "raw_output": str}.

    Returns impolite=None (with the raw text preserved) if the response isn't
    valid JSON or doesn't have the expected shape, instead of raising - a bad
    response should be flagged for review, not crash the run.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"impolite": None, "reason": None, "raw_output": raw}

    if not isinstance(parsed, dict):
        return {"impolite": None, "reason": None, "raw_output": raw}

    impolite = parsed.get("impolite")
    if not isinstance(impolite, bool):
        return {"impolite": None, "reason": None, "raw_output": raw}

    reason = parsed.get("reason")
    if not isinstance(reason, str):
        reason = None

    return {"impolite": impolite, "reason": reason, "raw_output": raw}
