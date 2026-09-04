"""Prompt construction and response parsing for the moral-civility zero-shot LLM
classifier. See measurement/morality_measurement.md for the construct definition.

Pool-building (build_classification_pool/build_position_index/build_context) is
construct-agnostic -- same ±1yr-AfD-window pool, same ±1-paragraph context lookup --
so this reuses impoliteness_lib's versions rather than duplicating them.
"""
import json

from impoliteness_lib import build_classification_pool, build_context, build_position_index
from morality_prompts import PROMPT_VERSION, PROMPTS, SYSTEM_PROMPT

__all__ = [
    "build_classification_pool", "build_context", "build_position_index",
    "build_prompt", "parse_response", "PROMPT_VERSION", "SYSTEM_PROMPT",
]

MORAL_CIVILITY_LABELS = {"neutral", "moralisch", "unmoralisch"}


def build_prompt(text: str, context: dict | None = None, prompt_version: str = PROMPT_VERSION) -> list[dict]:
    """Build the Ollama chat messages for classifying one paragraph's moral civility.

    Same context-window format as impoliteness_lib.build_prompt (prev/next paragraph,
    speaker label, same-speaker-turn flag) -- see that docstring for the format, and
    _ablate() in score_with_model.py for how variants strip parts of it. The
    ordnungsruf_follows hint is included for format-parity but isn't a criterion this
    prompt asks the model to use (it's a politeness-dimension signal, not a moral-
    civility one) -- SYSTEM_PROMPT never mentions it.
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

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def parse_response(raw: str) -> dict:
    """Parse the model's raw text response into
    {"moral_civility": str|None, "reason": str|None, "raw_output": str}.

    Returns moral_civility=None (with the raw text preserved) if the response isn't
    valid JSON, doesn't have the expected shape, or the value isn't one of the three
    known labels -- a bad response should be flagged for review, not crash the run.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"moral_civility": None, "reason": None, "raw_output": raw}

    if not isinstance(parsed, dict):
        return {"moral_civility": None, "reason": None, "raw_output": raw}

    moral_civility = parsed.get("moral_civility")
    if moral_civility not in MORAL_CIVILITY_LABELS:
        return {"moral_civility": None, "reason": None, "raw_output": raw}

    reason = parsed.get("reason")
    if not isinstance(reason, str):
        reason = None

    return {"moral_civility": moral_civility, "reason": reason, "raw_output": raw}
