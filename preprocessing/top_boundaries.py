"""
Detect Tagesordnungspunkt (agenda item) boundaries from presiding-officer speech and
build a paragraph-level side table assigning each paragraph a top_seq (sequential TOP
index within its protocol) and top_number_raw (best-effort parsed TOP number(s) as
announced). Joinable onto stateparl_v3_paragraphs.parquet by paragraph_id.
paragraphs.parquet itself is not modified in place.

Openers are detected only from affiliation == "pre" paragraphs (the presiding officer),
via three cues found across all 16 states by sampling stateparl_v3_paragraphs.parquet
directly:
  - rufe/aufrufe cue: a sentence containing both the noun ("Tagesordnungspunkt(e)",
    "Zusatztagesordnungspunkt", or RP's "Punkt N der Tagesordnung") and some form of the
    verb "aufrufen" — "Ich rufe Tagesordnungspunkt 11 auf", but also, critically, the
    fused subordinate-clause form "bevor ich den nächsten Tagesordnungspunkt aufrufe"
    (HB's dominant phrasing), where "ruf" trails the noun instead of leading it. Matched
    via co-occurrence within a sentence rather than a fixed left-to-right order.
  - komme-zu cue: "Wir kommen [jetzt/nun/damit] zu[m] [nächsten] Tagesordnungspunkt..."
    (RP/SL/NW).
  - bare heading line: a paragraph that starts with the noun, e.g. "Tagesordnungspunkt
    10:" followed by the title as the next pre paragraph (HE's dominant style).

A paragraph mentioning "vertagt"/"Konsensliste" (a batch readout of postponed items,
not a topic actually being opened) is excluded unless it also contains an aufrufen verb
— found via live sampling: ~170 of ~21k paragraphs starting with "Tagesordnungspunkt"
were pure postponement notices ("Tagesordnungspunkt 27 steht als vertagt auf der
Konsensliste"), which would otherwise each falsely start a new, contentless TOP.

Known gaps (left undetected, not silently mis-detected — see diagnostics below):
  - ~97 BB protocols have zero "pre" rows in the source data at all (a data-availability
    gap, not a detection-logic one).
  - A bare-numbered-heading style used in some NW protocols (and possibly other
    states/eras) — "Ich rufe auf:" as its own paragraph, followed by "1 Fragestunde" as
    the next paragraph, never using the word "Tagesordnungspunkt" for the opener itself.
    Detecting this reliably would need a much fuzzier "short paragraph starting with a
    bare number" heuristic, with real false-positive risk (vote tallies, Drucksache
    lists) — out of scope here; flagged in the diagnostics via the zero-opener-protocol
    rate per state.

Also extracts a best-effort document type (top_doc_type) and sponsor (top_sponsor) per
TOP, from the formal citation line that (usually) follows the opener — validated by
sampling the corpus directly, e.g. "Antrag der Fraktion der CDU und der Fraktion der FDP
Drucksache 17/16906" or "Beschlussempfehlung des Rechtsausschusses Drucksache 17/17026".
Two citation shapes, tried in order, plus a bare-title fallback for standing items that
have no sponsor at all:
  - Fraktion-sponsored: Antrag, Änderungsantrag, Entschließungsantrag, Dringlichkeitsantrag,
    Große/Kleine Anfrage, Wahlvorschlag, Aktuelle Stunde — "[Typ] [auf Antrag] der
    Fraktion/Abgeordneten X [und der Fraktion Y]". top_sponsor is the canonicalized party
    list (via nsc_rule_parser.canonicalize_party_list, reused as-is — its search-based
    matching resolves "der Fraktion der CDU" to "CDU" without needing to strip the filler
    words first), pipe-joined for joint sponsors.
  - Committee/government-originated: Gesetzentwurf, Beschlussempfehlung (und Bericht),
    Bericht, Zwischenbericht, Vorlage — "[Typ] des/der [Ausschuss/Landesregierung/...]".
    top_sponsor is the raw origin phrase (not party-canonicalized — committees aren't
    parties).
  - Bare standing-item title, no sponsor at all: Fragestunde, Aktuelle Stunde (also
    appears without a citation line), Regierungserklärung, Wahl der/von/des..., Vereidigung.
Not every TOP has a matching citation line nearby (many are procedural, or cited in a
form not covered here) — top_doc_type/top_sponsor are empty in that case, not guessed.

Output: DATA_ROOT/processed/top_boundaries.parquet
  Columns: paragraph_id, protocol_id, protocol_position, top_seq, top_number_raw,
    top_doc_type, top_sponsor
  top_seq: 0 for paragraphs before a protocol's first detected opener, else 1, 2, 3...
    per protocol — the reliable key. top_number_raw is a best-effort secondary field
    (pipe-joined for joint TOPs like "34|35", empty when no number is announced, e.g.
    unnumbered Zusatztagesordnungspunkt). top_doc_type/top_sponsor: see above, empty
    when no citation line is found for that TOP.

Usage:
    norm_env/bin/python preprocessing/top_boundaries.py
    norm_env/bin/python preprocessing/top_boundaries.py --state bb
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nsc_rule_parser import canonicalize_party_list, get_data_root

# ── regex patterns ───────────────────────────────────────────────────────────

_NOUN = r'(?:(?:zusatz)?tagesordnungspunkt(?:e|s)?|punkt\s+\d+\s*[a-zäöü]?\s+der\s+tagesordnung)'
_NOUN_RE = re.compile(_NOUN, re.I)

# "ruf(?:e|t|en)" as a bare substring (no left word-boundary) so it matches both the
# standalone verb ("rufe", "ruft", "rufen") and the fused separable-verb forms that
# occur in subordinate clauses ("aufrufe", "aufruft", "aufzurufen", "aufgerufen" all
# contain one of these three tails).
_VERB_RE = re.compile(r'ruf(?:e|t|en)', re.I)

_HEADING_RE = re.compile(rf'^\s*(?:zusatz)?tagesordnungspunkt(?:e|s)?\b', re.I)

_KOMME_RE = re.compile(
    rf'kommen?\w*\s*(?:wir\s+)?(?:jetzt\s+|nun\s+|damit\s+|dann\s+)?zu(?:m)?\s+'
    rf'(?:nächsten\s+)?{_NOUN}',
    re.I,
)

_POSTPONE_EXCL_RE = re.compile(r'vertagt|konsensliste', re.I)

# "Ich gehe davon aus, dass Einverständnis/Einvernehmen besteht, [X] zu [verbinden/
# behandeln/aufrufen]..." — a chair's procedural proposal to merge two items or
# schedule something for later, not a present opening. Found via live sampling: 30/30
# occurrences were previews/merge-proposals (e.g. "...am Schluss der Tagesordnung zu
# behandeln", "...mit den Tagesordnungspunkten ... zu verbinden"), none an actual
# opening. Unlike the postponement exclusion above, this can't be conditioned on "no
# verb present" — the proposal's own infinitive ("aufzurufen", "zu verbinden") is
# exactly what makes _VERB_RE fire in the first place, so it's excluded unconditionally
# rather than only when a verb is absent.
_FUTURE_PROPOSAL_EXCL_RE = re.compile(
    r'gehe davon aus, dass (?:Einverständnis|Einvernehmen) besteht', re.I,
)

_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

# A single TOP number, optionally sub-lettered ("6 b" -> "6", "b"). The trailing-letter
# group requires a negative lookahead for another word char, so it can't swallow the
# leading letter of a following connector word — plain `[a-zäöü]?` would greedily match
# the "u" in "7 und 40" and truncate the second number.
_NUM_UNIT = r'\d+(?:\s*[a-zäöü](?!\w))?'
_NUM_AFTER_NOUN_RE = re.compile(
    rf'(?:zusatz)?tagesordnungspunkt(?:e|s)?\s+'
    rf'({_NUM_UNIT}(?:\s*(?:,|und|bis|sowie)\s*{_NUM_UNIT})*)',
    re.I,
)
_NUM_PUNKT_DER_RE = re.compile(rf'punkt\s+({_NUM_UNIT})\s+der\s+tagesordnung', re.I)
_NUM_SPLIT_RE = re.compile(r'\s*(?:,|und|bis|sowie)\s*', re.I)

# Document-type citation lines — see module docstring for the three shapes and where
# each count came from. Order within each alternation doesn't matter: every type has a
# distinct leading substring (e.g. "Änderungsantrag" never starts with "Antrag" as its
# own word), so there's no first-alternative-wins ambiguity to worry about.
_SPONSOR_TYPES = (
    r'Aktuelle Stunde|Entschließungsantrag|Änderungsantrag|Dringlichkeitsantrag|'
    r'Große Anfrage|Kleine Anfrage|Wahlvorschlag|Antrag'
)
_SPONSOR_TYPE_RE = re.compile(
    rf'^({_SPONSOR_TYPES})\s*(?:auf Antrag\s+)?der\s+(?:Fraktion|Abgeordneten)\s+'
    rf'(.+?)(?=\s*Drucksache|\s*[Ii]n Verbindung|$)',
    re.I,
)

_ORIGIN_TYPES = r'Gesetzentwurf|Beschlussempfehlung(?: und Bericht)?|Zwischenbericht|Bericht|Vorlage'
_ORIGIN_TYPE_RE = re.compile(
    rf'^({_ORIGIN_TYPES})\s+(?:des|der)\s+'
    rf'(.+?)(?=\s*Drucksache|\s*[Ii]n Verbindung|$)',
    re.I,
)

# Standing agenda items with no Fraktion/committee sponsor at all — the title line
# itself is the type. An optional leading "N." / "N" (NW numbers these, e.g. "1
# Fragestunde") is allowed before the keyword. "Wahl" alone is too generic (would also
# match unrelated titles like "Wahlkreisreform"), so it requires "der/von/des" right
# after — matching what was validated against the corpus (508+294+184 hits).
_STANDING_TYPE_RE = re.compile(
    r'^(?:\d+\.?\s*)?(Fragestunde|Aktuelle Stunde|Regierungserklärung|Vereidigung\w*'
    r'|Wahl(?=\s+(?:der|von|des)\b))',
    re.I,
)

# Casing normalization: since every type regex above is case-insensitive (re.I), the
# captured text preserves whatever casing the source paragraph happened to use — and
# live sampling found protocol eras that spell headings in full caps ("AKTUELLE
# STUNDE") or lowercase ("antrag"), which would otherwise fragment one type into
# several differently-cased buckets downstream. Looked up by lowercased match text.
_CANONICAL_TYPES = [
    "Aktuelle Stunde", "Entschließungsantrag", "Änderungsantrag", "Dringlichkeitsantrag",
    "Große Anfrage", "Kleine Anfrage", "Wahlvorschlag", "Antrag",
    "Gesetzentwurf", "Beschlussempfehlung und Bericht", "Beschlussempfehlung",
    "Zwischenbericht", "Bericht", "Vorlage",
    "Fragestunde", "Regierungserklärung",
]
_CANONICAL_TYPE_MAP = {t.lower(): t for t in _CANONICAL_TYPES}


def _canonicalize_doc_type(raw: str) -> str:
    key = raw.lower()
    if key in _CANONICAL_TYPE_MAP:
        return _CANONICAL_TYPE_MAP[key]
    # "Vereidigung\w*" in _STANDING_TYPE_RE can capture a plural suffix ("Vereidigungen")
    # as part of the match, unlike the other alternatives — normalize any such variant
    # to the singular canonical form rather than adding every inflection to the map.
    if key.startswith("vereidigung"):
        return "Vereidigung"
    # matched text is bare "Wahl" (the regex requires a following der/von/des that
    # isn't part of the match itself), but "Wahlvorgang" is the more precise label
    # for the standing item -- an election is a procedure, not a person/object.
    if key == "wahl":
        return "Wahlvorgang"
    return raw


def extract_doc_type_and_sponsor(content: str) -> tuple[str, str]:
    """Best-effort (doc_type, sponsor) for a 'pre' paragraph, tried in the order
    described in the module docstring. ("", "") if nothing matches."""
    m = _SPONSOR_TYPE_RE.match(content)
    if m:
        parties = canonicalize_party_list(m.group(2))
        return _canonicalize_doc_type(m.group(1).strip()), '|'.join(parties)
    m = _ORIGIN_TYPE_RE.match(content)
    if m:
        return _canonicalize_doc_type(m.group(1).strip()), m.group(2).strip().rstrip('.')
    m = _STANDING_TYPE_RE.match(content)
    if m:
        return _canonicalize_doc_type(m.group(1).strip()), ''
    return '', ''


def is_top_opener(content: str) -> bool:
    """True if this (pre-affiliation) paragraph announces the start of a new TOP."""
    for sent in _SENT_SPLIT_RE.split(content):
        # A merge/scheduling proposal ("gehe davon aus, dass Einverständnis besteht...
        # zu verbinden/behandeln/aufzurufen") always co-occurs with a ruf-family verb —
        # that's exactly what makes it look like an opener — so it must be excluded
        # unconditionally, before has_verb is even checked.
        if _FUTURE_PROPOSAL_EXCL_RE.search(sent):
            continue
        has_verb = bool(_VERB_RE.search(sent))
        # A postponement/Konsensliste notice mentioning the TOP noun without an
        # aufrufen verb is a batch readout of already-shelved items, not an opener —
        # skip the whole sentence (including the bare-heading check) rather than
        # letting "Tagesordnungspunkt 27 steht als vertagt ..." match as a heading.
        if _POSTPONE_EXCL_RE.search(sent) and not has_verb:
            continue
        if _HEADING_RE.search(sent):
            return True
        if _NOUN_RE.search(sent) and has_verb:
            return True
        if _KOMME_RE.search(sent):
            return True
    return False


def extract_top_number_raw(content: str) -> str:
    """Best-effort TOP number(s) from an opener paragraph, pipe-joined for joint TOPs.
    Empty string if no number is announced (e.g. unnumbered Zusatztagesordnungspunkt)."""
    m = _NUM_PUNKT_DER_RE.search(content)
    if m:
        return m.group(1).replace(' ', '')
    m = _NUM_AFTER_NOUN_RE.search(content)
    if m:
        nums = [n.replace(' ', '') for n in _NUM_SPLIT_RE.split(m.group(1)) if n.strip()]
        return '|'.join(nums)
    return ''


def build_top_boundaries(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """
    paragraphs: must contain paragraph_id, protocol_id, protocol_position, affiliation,
    content. Returns one row per paragraph_id, ordered by (protocol_id, protocol_position):
    top_seq (0 before the first opener, else 1, 2, 3... per protocol), top_number_raw
    (broadcast from each group's opener row), and top_doc_type/top_sponsor (broadcast
    from the first 'pre' paragraph in the group whose citation line matches, which is
    usually — but not always — the opener row itself; see module docstring).
    """
    df = paragraphs.sort_values(["protocol_id", "protocol_position"]).reset_index(drop=True)
    is_pre = df["affiliation"] == "pre"

    is_opener = is_pre & df["content"].apply(is_top_opener)
    df["top_seq"] = is_opener.groupby(df["protocol_id"]).cumsum()

    opener_rows = df.loc[is_opener, ["protocol_id", "top_seq"]].copy()
    opener_rows["top_number_raw"] = df.loc[is_opener, "content"].apply(extract_top_number_raw)
    opener_rows = opener_rows.drop_duplicates(["protocol_id", "top_seq"], keep="first")

    extracted = df.loc[is_pre, "content"].apply(extract_doc_type_and_sponsor)
    doc_type, sponsor = zip(*extracted) if len(extracted) else ((), ())
    has_citation = pd.Series(False, index=df.index)
    has_citation.loc[is_pre] = [bool(t) for t in doc_type]
    df.loc[is_pre, "top_doc_type"] = doc_type
    df.loc[is_pre, "top_sponsor"] = sponsor

    type_rows = (
        df.loc[has_citation & (df["top_seq"] > 0), ["protocol_id", "top_seq", "top_doc_type", "top_sponsor"]]
        .drop_duplicates(["protocol_id", "top_seq"], keep="first")
    )

    df = df.drop(columns=["top_doc_type", "top_sponsor"])
    df = df.merge(opener_rows, on=["protocol_id", "top_seq"], how="left")
    df = df.merge(type_rows, on=["protocol_id", "top_seq"], how="left")
    df["top_number_raw"] = df["top_number_raw"].fillna("")
    df["top_doc_type"] = df["top_doc_type"].fillna("")
    df["top_sponsor"] = df["top_sponsor"].fillna("")

    return df[[
        "paragraph_id", "protocol_id", "protocol_position",
        "top_seq", "top_number_raw", "top_doc_type", "top_sponsor",
    ]]


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Detect Tagesordnungspunkt boundaries")
    ap.add_argument("--state", help="Process one state only (e.g. bb)")
    args = ap.parse_args()

    data_root = get_data_root()
    src = data_root / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet"
    out = data_root / "processed" / "top_boundaries.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading {src} ...")
    cols = ["paragraph_id", "protocol_id", "state", "protocol_position", "affiliation", "content"]
    para = pd.read_parquet(src, columns=cols)

    if args.state:
        para = para[para["state"] == args.state]
        print(f"  Filtered to state={args.state}: {len(para):,} rows")

    print("Detecting TOP openers ...")
    boundaries = build_top_boundaries(para)

    # ── diagnostics ──────────────────────────────────────────────────────────
    protocols = para[["protocol_id", "state"]].drop_duplicates()

    # top_seq is a per-protocol running count of openers, so each protocol's max is
    # exactly its opener count (0 if none detected).
    max_seq = boundaries.groupby("protocol_id")["top_seq"].max()
    protocols_with_opener = set(max_seq[max_seq > 0].index)

    protocols_with_pre = set(para.loc[para["affiliation"] == "pre", "protocol_id"])
    print(f"\n{len(protocols) - len(protocols_with_pre):,} of {len(protocols):,} protocols "
          f"have zero 'pre' (presiding officer) rows at all")
    print(f"Total openers detected: {int(max_seq.sum()):,}")

    top_groups = boundaries[boundaries["top_seq"] > 0].drop_duplicates(["protocol_id", "top_seq"])
    n_typed = (top_groups["top_doc_type"] != "").sum()
    print(f"TOPs with a detected doc_type: {n_typed:,} of {len(top_groups):,} "
          f"({n_typed / len(top_groups):.1%})")
    print("\ntop_doc_type distribution (detected TOPs only):")
    print(top_groups.loc[top_groups["top_doc_type"] != "", "top_doc_type"]
          .value_counts().to_string())

    print("\nZero-opener-protocol rate by state (of protocols with >=1 'pre' row):")
    protocols_pre_only = protocols[protocols["protocol_id"].isin(protocols_with_pre)].copy()
    protocols_pre_only["has_opener"] = protocols_pre_only["protocol_id"].isin(protocols_with_opener)
    by_state = (
        protocols_pre_only.groupby("state")["has_opener"]
        .apply(lambda s: 1 - s.mean())
        .sort_values(ascending=False)
    )
    print(by_state.apply(lambda x: f"{x:.1%}").to_string())

    boundaries.to_parquet(out, index=False)
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
