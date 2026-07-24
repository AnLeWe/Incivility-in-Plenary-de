"""Prompt construction and response parsing for the impoliteness pilot's zero-shot
LLM classifier. See docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md.
"""
import json

SYSTEM_PROMPT = (
    "Du bist Assistent für die Analyse von Redebeiträgen und Zwischenrufen aus "
    "deutschen Landtagen. Beurteile AUSSCHLIESSLICH Form und Ton der folgenden "
    "Äußerung, nicht den inhaltlichen Standpunkt.\n\n"
    "Als \"unhöflich\" gilt: Verstöße gegen parlamentarische Umgangsformen – "
    "Provokation, Schreien, Verspotten, Sarkasmus, vulgäre Sprache, ungebührliche "
    "Unterbrechungen, Beleidigungen, Bedrohung des öffentlichen Ansehens anderer "
    "Personen.\n\n"
    "Alles andere (neutrale sachliche Beiträge UND explizit höfliche Beiträge) "
    "gilt als \"nicht unhöflich\".\n\n"
    "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau diesem Format, ohne "
    "weiteren Text:\n"
    '{"impolite": true oder false, "reason": "<ein kurzer Satz auf Deutsch>"}'
)


def build_prompt(text: str) -> list[dict]:
    """Build the Ollama chat messages for classifying one paragraph."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
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
