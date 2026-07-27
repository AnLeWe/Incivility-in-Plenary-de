"""
Parse and clean interjection rows (affiliation == 'nsc') from StateParl v3 paragraphs.

Pipeline per row:
  1. classify_row_type  — tag document_reference / procedural / glocke / misattributed / garbled
  2. strip outer delimiter (state-specific: () or [])
  3. pre-normalize OCR hyphen-linebreak artifacts
  4. validated split — split only at recognised segment boundaries
  5. parse_segment — type keyword, qualifier, speaker/party extraction
  6. canonicalize party name

Output: DATA_ROOT/processed/nsc.parquet
  One row per segment, ordered by (state, period, nth, sequence_number, segment_idx).

Dataset version: StateParl v3 (2026-07-01, doi.org/10.7802/3062).
  Source: DATA_ROOT/raw/stateparl_v3_parquet/stateparl_v3_paragraphs.parquet
  Filter: affiliation == 'nsc' (was 'ijn' in v2)
  v3 columns used: paragraph_id, protocol_id, protocol_position, speech_id, state,
    period, nth, date, content  (speaker_paragraph, mandate_id loaded separately)
  v2 legacy file paragraphs_2010+.parquet is in DATA_ROOT/raw/ — do not use.

Usage:
    norm_env/bin/python preprocessing/nsc_rule_parser.py
    norm_env/bin/python preprocessing/nsc_rule_parser.py --state bb      # single state
    norm_env/bin/python preprocessing/nsc_rule_parser.py --sample 5000   # quick test

Affiliation codes in stateparl_v3_paragraphs.parquet (non-nsc, for reference):
  pre=president, gov=government, cdu/spd/grn/lin/fdp/afd/csu=major parties,
  pir=Piraten, frw=Freie Wähler, ssw=SSW, npd=NPD, ind=independent/fraktionslos,
  oth=other, büd/biw=Bürger in Wut (HB), bmv=minor MV party, lkr/bft/mrf/lfm=tiny

State-specific format notes (from sampling):
  BB: round (), sep ' - ', square brackets  e.g. Domres [DIE LINKE]: text
  BE: square [], sep ' – ', round brackets  e.g. Müller (SPD): text
  BW: round (), sep ' – ', space format     e.g. Abg. Hagel CDU: text
  BY: round (), sep ' – ', round brackets  (same as BE/HE pattern)
  HB: round (), sep ' – ', square brackets  (many document_reference/misattributed rows)
  HE: round (), sep ' – ', round brackets  — 674 rows severely garbled (encoding corruption, ± sign)
  HH: round (), sep ' – ', space format     e.g. Farid Müller GRÜNE: text
  MV: round (), sep ' – ', comma format     e.g. Dr. Weber, AfD: text; 'vonseiten der Fraktion' for faction attr.
  NI: round (), sep ' – '/' - ', square brackets
  NW: round (), sep ' – ', square brackets
  RP: round (), sep ' – ', comma format     e.g. Abg. Schnieder, CDU: text
  SH: round (), sep ' - '/' – ', square brackets
  SL: round (), sep ' – ', round brackets — BUT colon sometimes absent: (Abg. Name (Party))
  SN: round (), sep ' – ', comma format
  ST: round (), sep ' - '/' – ', comma format; GRÜ- NE OCR artifact common
  TH: round (), sep ' – ', comma format — many bare-name rows: (Abg. Tischner), no party

GAL (Grün-Alternative Liste Hamburg, active until ~2012) → canonical GRÜNE.
Linkspartei.PDS (BB period 4) → canonical LINKE (already caught by 'pds' pattern).

Patterns found in v3 sampling that required updates:
  Dafür/Dagegen (HB): 8,592 voting-record rows → classified as Prozedural
  Vorsitz: X (NW): 2,865 chair-change rows → classified as misattributed (via text not content)
  Zuruf des/der Abgeordneten X [Party] (BB): 22,702 no-colon → _NAME_SQUARE_NO_COLON
  Hört, hört! (10,954 rows): exclamation interjection → Ausruf bucket ((?!\\w) prevents 'Hörter')
  demonstrativ/fortgesetzt: new qualifier variants (1,887 + 1,237 rows)
  _IS_MISATTRIBUTED bug fixed (renamed from _IS_MISLABELLED 2026-07-27, see
  docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md): was searched on raw
    content (with outer parens) so ^-anchored pattern never matched; now searched on stripped text
  inj_type='Prozedural' (was 'procedural') — German capitalization consistency
  Multi-type: 'Heiterkeit und Beifall' → inj_type='Heiterkeit|Beifall' (|‑joined)
  Exclamations (Oh, Ja, Nein, Aha, Hört, Jawohl, Bravo, Pfui, Na) → Ausruf bucket
  Minister without party: 'Minister Reiche: text' → _MINISTER_COLON pattern
  Faction content: 'Zuruf von der SPD: Text!' → content_text='Text!' extracted
  'Beifall bei Abgeordneten der CDU' → party_raw stripped to 'CDU'
  New columns: role (Abgeordnete/r, Minister/in, …), title (Dr., Prof.)
  Glocke: speaker extracted from 'Glocke des Präsidenten' for glocke rows
"""

import os
import re
import sys
import argparse
from pathlib import Path

import pandas as pd

# ── environment ─────────────────────────────────────────────────────────────

def get_data_root() -> Path:
    if "DATA_ROOT" not in os.environ:
        try:
            from dotenv import load_dotenv, find_dotenv
            load_dotenv(find_dotenv())
        except ImportError:
            pass
    root = os.environ.get("DATA_ROOT")
    if not root or not Path(root).is_dir():
        sys.exit(f"DATA_ROOT not set or missing: {root!r}")
    return Path(root)


# ── state config ─────────────────────────────────────────────────────────────
# outer : round ()  or  square []
# sep   : regex for the segment separator
# fmt   : name+party format used in that parliament

STATE_CONFIG: dict[str, dict] = {
    "bb": dict(outer="round",  sep=r" - ",      fmt="square"),
    "be": dict(outer="square", sep=r" – ",      fmt="round"),
    "bw": dict(outer="round",  sep=r" – ",      fmt="space"),
    "by": dict(outer="round",  sep=r" – ",      fmt="round"),
    "hb": dict(outer="round",  sep=r" [–-] ",   fmt="square"),
    "he": dict(outer="round",  sep=r" – ",      fmt="round"),
    "hh": dict(outer="round",  sep=r" – ",      fmt="space"),
    "mv": dict(outer="round",  sep=r" – ",      fmt="comma"),
    "ni": dict(outer="round",  sep=r" [–-] ",   fmt="square"),
    "nw": dict(outer="round",  sep=r" – ",      fmt="square"),
    "rp": dict(outer="round",  sep=r" – ",      fmt="comma"),
    "sh": dict(outer="round",  sep=r" [–-] ",   fmt="square"),
    "sl": dict(outer="round",  sep=r" – ",      fmt="round_sl"),
    "sn": dict(outer="round",  sep=r" – ",      fmt="comma"),
    "st": dict(outer="round",  sep=r" [–-] ",   fmt="comma"),
    "th": dict(outer="round",  sep=r" [–-] ",   fmt="comma"),
}
_DEFAULT_CFG = dict(outer="round", sep=r" [–-] ", fmt="square")


# ── regex patterns ───────────────────────────────────────────────────────────

# OCR hyphen-linebreak artifacts: "word- Word" or "Wort- wort" → "wordWord" / "Wortwort"
_OCR_HYPHEN = re.compile(r'([A-ZÄÖÜa-zäöü])- ([A-ZÄÖÜa-zäöü])')

# Garbled rows: encoding corruption produces ± (HE v2 only; 0 rows in v3)
_IS_GARBLED = re.compile(r'±')

# Anchor: what may validly begin a new interjection segment after a separator
_ANCHOR = re.compile(
    r'(?:'
    r'beifall|zuruf|zwischenruf|unruhe|zustimmung|widerspruch|gegenruf'
    r'|lachen|gelächter|heiterkeit|glocke\w*|unmut|wortmeldung'
    r'|vereinzelt|lebhaft|anhaltend|allgemein|stark|weitere'
    r'|abg\.|abgeordnet\w*|minister\w*|präsident\w*|vizepräsident\w*'
    r'|senator\w*|staatssekretär\w*|dr\.|prof\.|frau|herr'
    r'|\[|\('
    r'|[A-ZÄÖÜ][a-zäöü]'
    r')',
    re.I,
)

# Interjection type keyword (anchored to segment start)
_TYPE_KW = re.compile(
    r'^(beifall|zuruf|zurüf|zwischenruf|unruhe|zustimmung|widerspruch|gegenruf'
    r'|lachen|gelächter|heiterkeit|glocke|glockenzeichen|unmut|wortmeldung'
    r'|hört(?!\w)|oh(?!\w)|ja(?!\w)|nein(?!\w)|aha(?!\w)'
    r'|jawohl(?!\w)|bravo(?!\w)|pfui(?!\w)|na(?!\w))\w*',
    re.I,
)

# All type keywords anywhere in segment (for multi-type detection)
_TYPE_KW_GLOBAL = re.compile(
    r'\b(beifall|zuruf|zurüf|zwischenruf|unruhe|zustimmung|widerspruch|gegenruf'
    r'|lachen|gelächter|heiterkeit|glocke|unmut|wortmeldung'
    r'|hört(?!\w)|oh(?!\w)|ja(?!\w)|nein(?!\w)|aha(?!\w)'
    r'|jawohl(?!\w)|bravo(?!\w)|pfui(?!\w)|na(?!\w))\w*',
    re.I,
)

# Connecting prepositions/particles that link a type keyword to the speaker/party that
# follows it (used only after a leading type keyword has already been confirmed —
# see _strip_leading_type_kw_run below).
_CONNECTOR_WORD = re.compile(
    r'^(?:und|von|bei|vonseiten|des|der|den|dem|abg\.?|abgeordneten?|fraktion(?:en)?)\s+',
    re.I,
)


def _strip_leading_type_kw_run(text: str) -> str:
    """Peel a leading type keyword — and, for compounds, a second keyword joined by
    "und" — plus any connecting prepositions/particles off the front of a segment,
    before name/party extraction is attempted. E.g. "Gegenruf des Abg. X" -> "X",
    "Zuruf von Y" -> "Y", "Heiterkeit und Zuruf von Z" -> "Z". Only one format
    (square, no-colon) previously did an equivalent strip; every other format left
    the keyword+preposition stuck in speaker_name. Only fires if the segment actually
    starts with a type keyword — returns text unchanged otherwise, so segments that
    already start with a name are never touched.
    """
    m = _TYPE_KW.match(text)
    if not m:
        return text
    text = text[m.end():].lstrip()
    m2 = re.match(r'^und\s+', text, re.I)
    if m2:
        rest = text[m2.end():]
        m3 = _TYPE_KW.match(rest)
        if m3:
            text = rest[m3.end():].lstrip()
    while True:
        m4 = _CONNECTOR_WORD.match(text)
        if not m4:
            break
        text = text[m4.end():]
    return text

# Types remapped to Ausruf bucket (exclamations / affirmations / rejections)
_AUSRUF_TYPES: frozenset[str] = frozenset(
    {"Oh", "Aha", "Ja", "Nein", "Hört", "Jawohl", "Bravo", "Pfui", "Na"}
)

# Qualifier that precedes the type keyword: "Vereinzelter Beifall ...", "Langanhaltender Beifall ..."
_QUALIFIER_PREFIX = re.compile(
    r'^(?:(?:lang\w*\s+)?(?:vereinzelt\w*|lebhaft\w*|anhaltend\w*|stark\w*'
    r'|allgemein\w*|weitere[rs]?\w*|demonstrativ\w*|fortgesetzt\w*)'
    r'|langanhaltend\w*)\s+',
    re.I,
)

# Optional qualifier before or after type keyword
_QUALIFIER = re.compile(
    r'\b(vereinzelt\w*|lebhaft\w*|anhaltend\w*|stark\w*|allgemein\w*|weitere[rs]?\w*'
    r'|demonstrativ\w*|fortgesetzt\w*)\b',
    re.I,
)

# Whole-house applause variants
_WHOLE_HOUSE = re.compile(
    r'des\s+(?:ganzen\s+)?hauses|im\s+hause|allgemeiner?\s+beifall|des\s+hauses',
    re.I,
)

# Named speaker — format variants ─────────────────────────────────────────────

# BB NI NW SH HB:  [Abg.] Name [Party]: text
_NAME_SQUARE = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\[([^\]]{1,50})\]\s*:(.*)',
    re.I | re.DOTALL,
)
# NI and others:  Name (Constituency) [Party]: text  — constituency in round, party in square
_NAME_SQUARE_CONSTITUENCY = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\([^)]{1,60}\)\s*\[([^\]]{1,50})\]\s*:(.*)',
    re.I | re.DOTALL,
)
# BB NI NW SH HB — no colon:  Zuruf des Abgeordneten Name [Party]  (22k BB rows)
_NAME_SQUARE_NO_COLON = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.?\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\[([^\]]{1,50})\]\s*\.?\s*$',
    re.I | re.DOTALL,
)
# BE BY HE:  [Abg.] Name (Party): text
_NAME_ROUND = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\(([^)]{1,50})\)\s*:(.*)',
    re.I | re.DOTALL,
)
# SL with colon:  Abg. Name (Party) :  (space before colon)
_NAME_ROUND_SL = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\(([^)]{1,50})\)\s+:(.*)',
    re.I | re.DOTALL,
)
# HE: Name (Constituency) (Party): text  — first bracket is a place name, skip it
_NAME_ROUND_CONSTITUENCY = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\([^)]{1,60}\)\s*\(([^)]{1,60})\)\s*:(.*)',
    re.I | re.DOTALL,
)
# SL without colon:  (Abg. Name (Party))  — pure attribution annotation, no content
_NAME_ROUND_NO_COLON = re.compile(
    r'^(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?)\s*\(([^)]{1,50})\)\s*\.?\s*$',
    re.I | re.DOTALL,
)
# MV RP SN ST TH:  [Zwischenruf] [Abg.] Name, Party: text
_NAME_COMMA = re.compile(
    r'^(?:zwischenruf\s+)?(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?),\s*([^:,]{1,60})\s*:(.*)',
    re.I | re.DOTALL,
)
# TH/ST: [Zwischenruf] [Abg.] Name, Party  (no colon, no content) — attribution only
_NAME_COMMA_NO_COLON = re.compile(
    r'^(?:zwischenruf\s+)?(?:(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+)*'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?),\s*((?-i:[A-ZÄÖÜ])[\wÄÖÜäöüß\s./]{1,40}?)\s*\.?\s*$',
    re.I | re.DOTALL,
)
# Bare name / role only, no party, no colon — e.g. "(Abg. Tischner)" or "(Minister Jost)"
_BARE_NAME_ONLY = re.compile(
    r'^(?:abg\.|abgeordnete[rn]?\.|frau\s|herr\s|dr\.\s|prof\.\s'
    r'|minister\w*\s|präsident\w*\s|vizepräsident\w*\s|staatssekretär\w*\s|senator\w*\s)?'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]{0,40}?)\s*\.?\s*$',
    re.I,
)

# [Role] Name: content — role keyword at start, no party bracket.
# Also covers "Abg. Name: content" and abbreviated "Sen" (Berlin).
# Optional Frau/Herr before the role keyword.
# Group 1=role keyword, 2=title (optional), 3=name, 4=content
_MINISTER_COLON = re.compile(
    r'^(?:(?:frau|herr)\s+)?'
    r'((?:vize)?minister(?:präsident(?:in)?)?|senator(?:in)?|sen\b'
    r'|abg\.|abgeordnete[rn]?\.?'
    r'|(?:erste[rn]?\s+)?bürgermeister'
    r'|staatssekretär(?:in)?|parlamentarische[rs]?\s+staatssekretär(?:in)?'
    r'|staatsminister)\w*'
    r'\s+(?:(?:frau|herr)\s+)?(?:((?:prof\.\s*)?dr\.)\s+)?'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]{0,40}?)\s*:\s*(.*)',
    re.I | re.DOTALL,
)

# Name, [government role ...]: content — name-first variant used by some officials.
# "[^:]*" absorbs the full role title including department (e.g. "Minister des Innern").
# Group 1=title, 2=name, 3=role keyword, 4=content
_MINISTER_COMMA = re.compile(
    r'^(?:(?:frau|herr)\s+)?'
    r'(?:((?:prof\.\s*)?dr\.)\s+)?'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]*?),\s*'
    r'((?:vize)?minister\w*|senator\w*|bürgermeister\w*'
    r'|staatssekretär\w*|parlamentarische[rs]?\s+staatssekretär\w*|staatsminister\w*'
    r'|ministerpräsident\w*)'
    r'[^:]*:\s*(.*)',
    re.I | re.DOTALL,
)

# Minister/government role without a colon — pure attribution, no spoken content:
# "Zuruf des Ministers Dr. Alois Rhiel", "Widerspruch von Ministerpräsident Peer
# Steinbrück". Without this, these fall through to the generic party-guess fallback
# in parse_segment, which resolves the bare role word to GOV and silently drops the
# actual named minister. Mirrors _MINISTER_COLON's role list, anchored to end-of-string
# instead of a colon (segment has already had its leading type keyword + connecting
# preposition stripped by the time this is tried, same as _MINISTER_COLON).
# Group 1=role keyword, 2=title (optional), 3=name
_MINISTER_NO_COLON = re.compile(
    r'^((?:vize)?minister(?:präsident(?:in)?)?|senator(?:in)?'
    r'|(?:erste[rn]?\s+)?bürgermeister|staatssekretär(?:in)?'
    r'|parlamentarische[rs]?\s+staatssekretär(?:in)?|staatsminister)\w*'
    r'\s+(?:(?:frau|herr)\s+)?(?:((?:prof\.\s*)?dr\.)\s+)?'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß\s.\-]{0,40}?)\s*\.?\s*$',
    re.I | re.DOTALL,
)

# Role / honorific / title prefixes for speaker_name cleanup
_ROLE_PREFIX_RE = re.compile(
    r'^(abg\.?|abgeordnete[rn]?\.?'
    r'|(?:vize)?minister(?:präsident(?:in)?)?\.?'
    r'|senator(?:in)?\.?|bürgermeister(?:in)?\.?'
    r'|staatssekretär(?:in)?\.?|schriftführer(?:in)?\.?'
    r'|parlamentarische[rs]?\s+staatssekretär(?:in)?\.?)\s+',
    re.I,
)
_TITLE_RE = re.compile(r'^((?:prof\.\s*)?dr\.)\s+', re.I)
_HONORIFIC_RE = re.compile(r'^(?:frau|herr)\s+', re.I)

# For space-format states (BW, HH): anchor on known party token
_KNOWN_PARTY = re.compile(
    r'\b(SPD|CDU|CSU|AfD|FDP(?:/DVP)?|GRÜNE\w*|LINKE\w*|PIRATEN\w*'
    r'|SSW|NPD|REP\b|FREIE\s*WÄHLER|BVB(?:/FW)?|GAL|BÜNDNIS\s*\w*|BSW|fraktionslos\w*)\b',
    re.I,
)

# Faction attribution without named speaker (covers "bei der SPD", "von den GRÜNEN",
# "vonseiten der Fraktion der CDU", "von den Koalitionsfraktionen"). Captures greedily
# to the end of the segment (like other content-capture groups in this module, e.g.
# _NAME_ROUND's ".*$") rather than a narrow character class — a narrow class silently
# discarded everything from the first ':' onward, losing real quoted content in rows
# like "Zuruf von der CDU: Das ist Blödsinn!" (the colon-split logic just below this
# match already handles that case correctly once the colon is actually captured).
_FACTION_PREP = re.compile(
    r'(?:vonseiten|bei|von)\s+(?:(?:fraktion(?:en)?\s+)?(?:der|den|dem|des)\s+)?(.+)',
    re.I | re.DOTALL,
)
# Strip "Abgeordneten der/des/von" prefix within faction party_raw
_ABG_FACTION_RE = re.compile(r'^abgeordneten?\s+(?:der|des|von)\s+', re.I)
# Leading German definite article before a party list with no preposition,
# e.g. "Beifall der FDP, der SPD ..." — "der" is not a party token.
_LEADING_ARTICLE_RE = re.compile(r'^(?:der|die|das|den|dem|des)\s+', re.I)

# Row-type signals (applied to stripped text before parsing)
# document_reference (renamed from "noise" 2026-07-27): these aren't reaction content at
# all, just bibliographic/procedural document references (bill numbers, agenda items,
# reading-stage markers) that got affiliation == "nsc" upstream in the source StateParl
# corpus by mistake — an upstream labeling artifact, not interpretive work of this parser's.
_IS_DOCUMENT_REFERENCE = re.compile(
    r'^(?:drucksache\s+\d|tagesordnungspunkt\s+\d|\d+\.\s+(?:erste|zweite|dritte)\s+lesung'
    r'|abstimmung\s+über\s+den\s+gesetzentwurf|beschlussfassung'
    r'|siehe\s+anlage|abänderungsantrag)',
    re.I,
)
_IS_PROCEDURAL = re.compile(
    r'namensaufruf|wahlhandlung|abstimmungsliste|namentliche\s+abstimmung'
    r'|fortsetzung\s+der\s+sitzung|unterbrechung\s+der\s+sitzung'
    r'|die\s+sitzung\s+wird\s+(?:unter|fort)'
    r'|^(?:dafür|dagegen)\b'
    r'|^schluss\s*:'
    r'|^wiederaufnahme\s+der\s+sitzung'
    r'|^zu\s+protokoll\s*:'
    r'|^unterbrechung\s+von\s+\d'
    r'|meldet\s+sich\s+zu'
    r'|^stimmabgabe\s+von\s+\d'
    r'|^(?:erste|zweite|dritte)\s+beratung\s+(?:in\s+der|\d)',
    re.I,
)
_STAGE_VERBS = (
    r'steht\s+am\s+mikrofon|übergibt|überreicht|nickt\b|lacht\b|applaudiert'
    r'|spricht\s+bei\s+abgeschaltetem|niest\b|schüttelt\b|deutet\b|begibt\s+sich'
    r'|verlässt\b|betritt\b|unterhält\b'
)
# misattributed (renamed from "mislabelled" 2026-07-27): reflects that the *source
# data's* affiliation == "nsc" tag is wrong for these rows — they're narrative
# stage-direction text (describing a named individual's physical action, chair-handover
# narration, ...) mistagged as a reaction, not that this parser mislabeled anything.
_IS_MISATTRIBUTED = re.compile(
    r'^(?:meine\s+damen|ich\s+(?:eröffne|rufe\s+auf|schließe|erteile)'
    r'|die\s+berichterstattung\s+wurde'
    r'|vorsitz\s*:'
    # "Der/Die Abgeordnete X verb"
    r'|(?:der|die)\s+abgeordnete[rn]?\s+\w.*(?:steht|wendet|hält|zeigt|spricht|geht)'
    # "Word(s) verb"  (no brackets or commas between name and verb)
    r'|(?:\w+\s+){1,3}(?:' + _STAGE_VERBS + r')'
    # "Name [Party] verb"  (bracket format)
    r'|[\wÄÖÜäöüß][\wÄÖÜäöüß\s.]{1,30}\[[^\]]{1,30}\]\s+(?:' + _STAGE_VERBS + r')'
    # "Name, Party, verb"  (comma format; [^,] allows multi-word party names)
    r'|(?:[\wÄÖÜäöüß]+\s+){1,3}[\wÄÖÜäöüß\-]+,\s*[^,]{2,35},\s*(?:' + _STAGE_VERBS + r')'
    # chair-change: "[Erste] [Vize]Präsident/in Name(n) übernimmt den Vorsitz"
    r'|(?:erste[rn]?\s+)?(?:\w+)?präsident\w*\s+(?:\w+\s+){1,3}übernimmt\s+den\s+vorsitz'
    # collective narrative
    r'|(?:zahlreiche|viele|mehrere|einige)\s+(?:mitglieder|abgeordnete|vertreter)'
    r'|die\s+abgeordneten\s+(?:erheben|verlassen|betreten|stehen))',
    re.I,
)
_IS_GLOCKE = re.compile(r'\bglocke\w*\b', re.I)

# Extract Präsident speaker from glocke rows: "Glocke des Präsidenten"
_GLOCKE_SPEAKER_RE = re.compile(
    r'\bglocke\w*\b.*?\bde[rs]\s+((?:vize)?präsident(?:in)?)',
    re.I,
)


# ── party canonicalization ───────────────────────────────────────────────────

_PARTY_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r'bündnisgrün\w*',           re.I), "GRÜNE"),
    (re.compile(r'bündnis\s*90\w*',          re.I), "GRÜNE"),
    (re.compile(r'b\s*90\s*/\s*grün\w*',     re.I), "GRÜNE"),
    (re.compile(r'freie\w*\s*wähler\w*',     re.I), "FW"),
    (re.compile(r'freie\s+demokrat\w*',      re.I), "FDP"),
    (re.compile(r'fdp(?:/dvp)?',             re.I), "FDP"),
    (re.compile(r'f\.d\.p\.',                re.I), "FDP"),
    (re.compile(r'die\s+linke\w*',           re.I), "LINKE"),
    (re.compile(r'linke\w*',                 re.I), "LINKE"),
    (re.compile(r'pds',                      re.I), "LINKE"),
    (re.compile(r'bsw|wagenknecht',          re.I), "BSW"),
    (re.compile(r'grün\w*',                  re.I), "GRÜNE"),
    (re.compile(r'gal\b',                    re.I), "GRÜNE"),
    (re.compile(r'bvb(?:/fw)?',              re.I), "FW"),
    (re.compile(r'spd',                      re.I), "SPD"),
    (re.compile(r'cdu',                      re.I), "CDU"),
    (re.compile(r'csu',                      re.I), "CSU"),
    (re.compile(r'afd',                      re.I), "AfD"),
    (re.compile(r'ssw',                      re.I), "SSW"),
    (re.compile(r'npd',                      re.I), "NPD"),
    (re.compile(r'piraten\w*',               re.I), "PIRATEN"),
    (re.compile(r'fraktionslos\w*',          re.I), "FRAKTIONSLOS"),
    (re.compile(r'koalitionsfraktion\w*',    re.I), "KOALITION"),
    (re.compile(r'regierungsfraktion\w*',    re.I), "KOALITION"),
    (re.compile(r'regierungspartei\w*',      re.I), "KOALITION"),
    (re.compile(r'oppositionsfraktion\w*',   re.I), "OPPOSITION"),
]


# Government/executive actors — ministers, the cabinet collectively ("Staatsregierung" /
# "Landesregierung" / "Regierungsbank"), mayors, senators (city-states). Distinct from
# OTHER: these are identifiable government actors, not an unmapped/unknown party, and
# should map to affiliation "gov" (same as _ROLE_TO_AFF does for the primary speaker).
# "ministerpräsident" is checked as part of this pattern (not _PRESIDING_PATTERN) since
# the Minister-President heads the executive, unlike a bare "Präsident/in" (chamber speaker).
_GOV_PATTERN = re.compile(
    r'staatsregierung\w*|landesregierung\w*|regierungsbank\w*'
    r'|ministerpräsident\w*|(?:vize)?minister\w*|staatsminister\w*'
    r'|senator(?:in)?\w*|(?:erste[rn]?\s+)?bürgermeister\w*'
    r'|(?:parlamentarische[rs]?\s+)?staatssekretär(?:in)?\w*',
    re.I,
)
# Presiding officer of the chamber (Landtagspräsident/in) — legislature leadership,
# distinct from the executive/government. Checked after _GOV_PATTERN so
# "Ministerpräsidentin" resolves to GOV, not PRE, despite containing "präsident".
_PRESIDING_PATTERN = re.compile(
    r'(?:vize)?präsident\w*|schriftführer\w*',
    re.I,
)


def canonicalize_party(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    for pat, canonical in _PARTY_MAP:
        if pat.search(raw):
            return canonical
    if _GOV_PATTERN.search(raw):
        return "GOV"
    if _PRESIDING_PATTERN.search(raw):
        return "PRE"
    return "OTHER"


def _is_real_party_token(text: str) -> bool:
    """True if `text` alone already resolves to a genuine party/institutional actor —
    used to reject comma-format 'name' matches that are actually just another party in
    a list, e.g. "Beifall CDU, DIE LINKE" misread by _NAME_COMMA_NO_COLON as
    speaker_name="CDU", party="DIE LINKE" (the 2-item-list shape happens to fit the
    "Name, Party" pattern exactly). A real surname essentially never canonicalizes to
    anything but OTHER, so this has negligible false-rejection risk."""
    c = canonicalize_party(text)
    return c not in ("", "OTHER")


def canonicalize_party_list(raw: str) -> list[str]:
    # Split only on "und"/"sowie"/comma — NOT on "/", since several joint-list party
    # names use a slash (FDP/DVP, B90/GRÜNE, BVB/FW) and _PARTY_MAP has patterns
    # specifically written to match those whole compounds. Splitting on "/" first would
    # defeat those patterns, e.g. canonicalize_party("FDP/DVP") == "FDP" directly, but
    # splitting into ["FDP","DVP"] first turns it into "FDP|OTHER" instead.
    parts = re.split(r'\s+(?:und|sowie)\s+|\s*,\s*', raw)
    seen, result = set(), []
    for p in parts:
        p = p.strip().rstrip(".")
        if not p:
            continue
        c = canonicalize_party(p)
        # Whole fragment didn't match a compound-aware pattern — only now fall back to
        # splitting on "/" and canonicalizing each half separately.
        if c == "OTHER" and "/" in p:
            for sub in p.split("/"):
                sub = sub.strip()
                if not sub:
                    continue
                sc = canonicalize_party(sub)
                if sc and sc not in seen:
                    seen.add(sc)
                    result.append(sc)
            continue
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


# ── role / title helpers ─────────────────────────────────────────────────────

_ROLE_TO_AFF: dict[str, str] = {
    "Ministerpräsident/in": "gov",
    "Minister/in":          "gov",
    "Senator/in":           "gov",
    "Bürgermeister/in":     "gov",
    "Staatssekretär/in":    "gov",
    "Präsident/in":         "pre",
    "Vizepräsident/in":     "pre",
}

_PARTY_TO_AFF: dict[str, str] = {
    "CDU":          "cdu",
    "CSU":          "csu",
    "SPD":          "spd",
    "GRÜNE":        "grn",
    "LINKE":        "lin",
    "FDP":          "fdp",
    "AfD":          "afd",
    "BSW":          "bsw",
    "FW":           "frw",
    "SSW":          "ssw",
    "NPD":          "npd",
    "PIRATEN":      "pir",
    "FRAKTIONSLOS": "ind",
    "GOV":          "gov",
    "PRE":          "pre",
    "OTHER":        "oth",
}


def _derive_affiliation(role: str, party_canonical: str) -> str:
    """Map parsed role/party to StateParl affiliation code(s), |-joined for multi-party."""
    if role in _ROLE_TO_AFF:
        return _ROLE_TO_AFF[role]
    if party_canonical:
        codes = [_PARTY_TO_AFF.get(p, "") for p in party_canonical.split("|")]
        codes = sorted(set(c for c in codes if c))
        if codes:
            return "|".join(codes)
    return ""


def _normalize_role(raw: str) -> str:
    r = raw.strip().lower().rstrip(".")
    if r.startswith("ministerpräsident"):  return "Ministerpräsident/in"
    if r.startswith("staatsminister"):     return "Minister/in"
    if "staatssekretär" in r:             return "Staatssekretär/in"
    if r.startswith("minister"):          return "Minister/in"
    if r.startswith("senator") or r == "sen": return "Senator/in"
    if "bürgermeister" in r:             return "Bürgermeister/in"
    if r.startswith("vizepräsident"):     return "Vizepräsident/in"
    if r.startswith("schriftführer"):     return "Schriftführer/in"
    if r.startswith("abg") or r.startswith("abgeordnet"):  return "Abgeordnete/r"
    return ""


def _extract_prefixes(name: str) -> tuple[str, str, str]:
    """Strip honorific, role prefix, and title from a raw speaker name.
    Returns (clean_name, role, title)."""
    name = _HONORIFIC_RE.sub("", name, count=1).strip()
    role = ""
    m = _ROLE_PREFIX_RE.match(name)
    if m:
        role = _normalize_role(m.group(1))
        name = name[m.end():].strip()
    title = ""
    m = _TITLE_RE.match(name)
    if m:
        title = m.group(1)
        name = name[m.end():].strip()
    return name, role, title


# ── core parsing functions ───────────────────────────────────────────────────

# Row-type categories that are not real interjection/reaction content and should be
# excluded from any interjection-level analysis or classification. Single source of
# truth — import this rather than re-hardcoding the set (previously duplicated across
# nsc_llm_explode.py, analysis/nsc_analysis.ipynb, and this module's own diagnostics,
# which is how the capitalized "Glocke" nsc_type value ended up silently uncovered by
# any of them — see docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md).
# Note: this only covers the lowercase row-type-level "glocke" (a row that's entirely
# and only about the chair's bell); the capitalized "Glocke" nsc_type tag (a reaction-type
# tag on an otherwise-real interjection row) is deliberately NOT in this set — it's a
# retained, meaningful signal, not noise.
NON_INTERJECTION_TYPES = {"glocke", "Prozedural", "misattributed", "document_reference", "garbled"}


def classify_row_type(content: str) -> str:
    if _IS_GARBLED.search(content):
        return "garbled"
    text = content.strip().lstrip('([').rstrip(')]').strip()
    if _IS_DOCUMENT_REFERENCE.search(text):
        return "document_reference"
    if _IS_PROCEDURAL.search(text):
        return "Prozedural"
    if _IS_MISATTRIBUTED.search(text):
        return "misattributed"
    if _IS_GLOCKE.search(text) and len(text) < 80:
        return "glocke"
    return "interjection"


def strip_outer(content: str, outer: str) -> str:
    s = content.strip()
    if outer == "round" and s.startswith("(") and s.endswith(")"):
        return s[1:-1].strip()
    if outer == "square" and s.startswith("[") and s.endswith("]"):
        return s[1:-1].strip()
    return s.lstrip("([").rstrip(")]").strip()


def normalize_ocr(text: str) -> str:
    return _OCR_HYPHEN.sub(lambda m: m.group(1) + m.group(2), text)


def validated_split(text: str, sep: str) -> list[str]:
    split_pat = re.compile(sep + r'(?=' + _ANCHOR.pattern + r')', re.I)
    parts = split_pat.split(text)
    return [p.strip() for p in parts if p.strip()]


def extract_named_speaker(segment: str, fmt: str) -> dict:
    """
    Try to extract (speaker_name, party_raw, content_text, role, title) from a segment.
    Returns dict with those keys; empty strings if unmatched.
    """
    result = {"speaker_name": "", "party_raw": "", "content_text": "", "role": "", "title": ""}

    # Strip a leading type keyword + connecting preposition (e.g. "Gegenruf des Abg.",
    # "Zuruf von", "Heiterkeit und Zuruf von") before any extraction is attempted, so it
    # never ends up stuck in speaker_name. Applies uniformly across every format and to
    # both the Minister checks below and the format-specific branches further down.
    segment = _strip_leading_type_kw_run(segment)

    # Minister/government role without party brackets — applies across all formats
    m = _MINISTER_COLON.match(segment)
    if m:
        role_raw  = m.group(1)
        title_raw = (m.group(2) or "").strip()
        name_raw  = m.group(3).strip()
        content   = m.group(4).strip()
        name_raw  = _HONORIFIC_RE.sub("", name_raw, count=1).strip()
        name_raw  = re.sub(r'\s+und\s+.*', '', name_raw, flags=re.I).strip()
        tm = _TITLE_RE.match(name_raw)
        if tm and not title_raw:
            title_raw = tm.group(1)
            name_raw  = name_raw[tm.end():].strip()
        result.update(speaker_name=name_raw, role=_normalize_role(role_raw),
                      title=title_raw, content_text=content)
        return result

    # Name, [government role ...]: content — name-first variant (e.g. "Reul, Minister des Innern:")
    m = _MINISTER_COMMA.match(segment)
    if m:
        title_raw = (m.group(1) or "").strip()
        name_raw  = m.group(2).strip()
        role_raw  = m.group(3).strip()
        content   = m.group(4).strip()
        result.update(speaker_name=name_raw, role=_normalize_role(role_raw),
                      title=title_raw, content_text=content)
        return result

    # Minister/government role without a colon — pure attribution, no spoken content
    m = _MINISTER_NO_COLON.match(segment)
    if m:
        role_raw  = m.group(1)
        title_raw = (m.group(2) or "").strip()
        name_raw  = m.group(3).strip()
        name_raw  = _HONORIFIC_RE.sub("", name_raw, count=1).strip()
        tm = _TITLE_RE.match(name_raw)
        if tm and not title_raw:
            title_raw = tm.group(1)
            name_raw  = name_raw[tm.end():].strip()
        result.update(speaker_name=name_raw, role=_normalize_role(role_raw), title=title_raw)
        return result

    def _post(name: str, existing_role: str = "") -> tuple[str, str, str]:
        """Strip prefixes from extracted name; return (name, role, title)."""
        n, r, t = _extract_prefixes(name)
        return (n or name), (existing_role or r), t

    if fmt == "square":
        m = _NAME_SQUARE.match(segment)
        if m:
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip(),
                          content_text=m.group(3).strip())
            return result
        # Name (Constituency) [Party]: text  — e.g. "Wulff (Osnabrück) [CDU]: ..."
        m = _NAME_SQUARE_CONSTITUENCY.match(segment)
        if m:
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip(),
                          content_text=m.group(3).strip())
            return result
        rest = _TYPE_KW.sub("", segment, count=1).strip()
        rest = re.sub(r"^de[rms]\s+", "", rest, flags=re.I).strip()
        m = _NAME_SQUARE_NO_COLON.match(rest)
        if m:
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip())
        return result

    if fmt in ("round", "round_sl"):
        m = (_NAME_ROUND_SL if fmt == "round_sl" else _NAME_ROUND).match(segment)
        if m:
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip(),
                          content_text=m.group(3).strip())
            return result
        if fmt == "round_sl":
            m = _NAME_ROUND.match(segment)
            if m:
                name, role, title = _post(m.group(1).strip())
                result.update(speaker_name=name, role=role, title=title,
                              party_raw=m.group(2).strip(),
                              content_text=m.group(3).strip())
                return result
        # Name (Constituency) (Party): text  — HE and similar double-bracket formats
        m = _NAME_ROUND_CONSTITUENCY.match(segment)
        if m:
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip(),
                          content_text=m.group(3).strip())
            return result
        m = _NAME_ROUND_NO_COLON.match(segment)
        if m:
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip())
        return result

    if fmt == "comma":
        m = _NAME_COMMA.match(segment)
        # Reject when the "name" slot is itself a real party/institutional token —
        # a 2-item party list ("CDU, DIE LINKE") fits this pattern's shape exactly
        # but isn't a named speaker at all (see _is_real_party_token).
        if m and not _is_real_party_token(m.group(1).strip()):
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip(),
                          content_text=m.group(3).strip())
            return result
        m = _NAME_COMMA_NO_COLON.match(segment)
        if m and not _is_real_party_token(m.group(1).strip()):
            name, role, title = _post(m.group(1).strip())
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=m.group(2).strip())
        return result

    if fmt == "space":
        pm = _KNOWN_PARTY.search(segment)
        if pm:
            name_part = segment[: pm.start()].strip()
            name_part = re.sub(
                r'^(?:abg|abgeordnete[rn]?|frau|herr|dr|prof)\.\s+', '',
                name_part, flags=re.I,
            ).strip().rstrip(":")
            after_party = segment[pm.end():].strip().lstrip(":").strip()
            name, role, title = _post(name_part)
            result.update(speaker_name=name, role=role, title=title,
                          party_raw=pm.group(0),
                          content_text=after_party)
        return result

    return result


def parse_segment(segment: str, fmt: str) -> dict:
    """Parse one interjection segment into structured fields."""
    seg = segment.strip()

    # Text before the first ':' is the narrator's/stenographer's own description;
    # text after it is quoted spoken content. Structural signals below (whole-house,
    # qualifier, multi-type keywords) describe the REACTION as narrated, not whatever
    # the quoted speaker happens to say — e.g. "Jörg Bode [FDP]: Es gibt nur Beifall
    # bei dieser Seite des Hauses!" must not set is_whole_house=True just because his
    # quoted words happen to contain "des Hauses". Segments with no colon (attribution
    # only, no content_text) are unaffected — scan_text falls back to the full segment.
    colon_idx  = seg.find(":")
    scan_text  = seg[:colon_idx].rstrip() if colon_idx != -1 else seg

    is_whole_house = bool(_WHOLE_HOUSE.search(scan_text))

    # Primary type keyword (^-anchored, drives party-extraction offset)
    type_m  = _TYPE_KW.match(seg)
    _seg_kw = seg
    if not type_m:
        _stripped = _QUALIFIER_PREFIX.sub("", seg, count=1)
        if _stripped != seg:
            type_m = _TYPE_KW.match(_stripped)
            if type_m:
                _seg_kw = _stripped
    primary_type = type_m.group(1).capitalize() if type_m else ""

    qual_m    = _QUALIFIER.search(scan_text)
    qualifier = qual_m.group(1).lower() if qual_m else ""

    speaker_info = extract_named_speaker(seg, fmt)
    is_named     = bool(speaker_info["speaker_name"])

    # Glocke segments ("Glocke des Präsidenten") never carry a real party/faction
    # attribution — "des Präsidenten" names the chair ringing the bell, not a party
    # reacting. Extract the presiding officer directly (same regex used for standalone
    # row-level glocke rows) so the identity/role is preserved correctly, instead of
    # letting the party-guess fallback below mistake the bare role noun for a party
    # (it resolves to a real canonical value, PRE, so the non-OTHER guard there
    # doesn't catch it — see the primary_type != "Glocke" guard added below too).
    if primary_type == "Glocke" and not is_named:
        gm = _GLOCKE_SPEAKER_RE.search(seg)
        if gm:
            speaker_info["speaker_name"] = gm.group(1).strip()
            speaker_info["role"] = "Präsident/in"
            is_named = True

    # Bare-name fallback: short segment with no type keyword and no matched speaker
    if not is_named and not primary_type and len(seg) < 60:
        bm = _BARE_NAME_ONLY.match(seg)
        if bm:
            name_candidate = bm.group(1).strip()
            if name_candidate and name_candidate[0].isupper():
                speaker_info["speaker_name"] = name_candidate
                is_named = True

    party_raw      = speaker_info["party_raw"]
    faction_content = ""

    if not is_named:
        fp = _FACTION_PREP.search(seg)
        if fp:
            raw_faction = fp.group(1).strip().rstrip(".")
            # Extract spoken content after ": text" if present
            colon_pos = raw_faction.find(":")
            if colon_pos != -1:
                faction_content = raw_faction[colon_pos + 1:].strip()
                raw_faction = raw_faction[:colon_pos].strip().rstrip(",").rstrip(".")
            # Strip "Abgeordneten der/des/von" prefix
            raw_faction = _ABG_FACTION_RE.sub("", raw_faction).strip()
            party_raw = raw_faction
            # Text before "bei/von ..." is the spoken content (e.g. "Richtig! bei CDU")
            pre = seg[:fp.start()].strip().rstrip(",").rstrip(".")
            if pre and not faction_content:
                faction_content = pre
        elif primary_type and primary_type != "Glocke":
            # Glocke is excluded here regardless of whether the extraction above
            # matched — a bell has no party, full stop; see the comment there.
            after_kw = _seg_kw[type_m.end():].strip().lstrip(",").strip()
            # Bare ": spoken content" after type keyword (no faction preposition)
            if after_kw.startswith(":"):
                faction_content = after_kw[1:].strip()
            else:
                # Strip a leading article before checking for a party list,
                # e.g. "Beifall der FDP, der SPD und ..." — "der" isn't a party token.
                # Require the stripped text to actually resolve to a real (non-OTHER)
                # party before accepting it — otherwise role/name attributions like
                # "Zuruf des Ministers Stratthaus" would fabricate a bogus OTHER party
                # where none should be captured at all.
                after_kw_stripped = _LEADING_ARTICLE_RE.sub("", after_kw, count=1)
                if (after_kw_stripped and after_kw_stripped[0].isupper()
                        and any(p != "OTHER" for p in canonicalize_party_list(after_kw_stripped))):
                    party_raw = after_kw_stripped

    parties = canonicalize_party_list(party_raw) if party_raw else []

    # Multi-type detection: reuses scan_text (narrator-only, before the first ':')
    # computed above. E.g. "Heiterkeit und Beifall bei der SPD" → {"Heiterkeit","Beifall"}
    # but "Klein [SPD]: Ja, natürlich!" → only "Klein [SPD]" scanned → no spurious Ausruf.
    all_kws    = [m.group(1).capitalize() for m in _TYPE_KW_GLOBAL.finditer(scan_text)]
    # Remap exclamation bucket and deduplicate
    unique_kws: set[str] = {
        ("Ausruf" if k in _AUSRUF_TYPES else k) for k in all_kws
    }
    # Sort alphabetically so the joined label is independent of source phrasing order —
    # "Heiterkeit und Beifall" and "Beifall und Heiterkeit" both → "Beifall|Heiterkeit".
    unique_kws_sorted = sorted(unique_kws)

    if unique_kws_sorted:
        nsc_type = "|".join(unique_kws_sorted)
    elif is_named:
        nsc_type = "Zwischenruf"
    elif parties:
        # Party attribution found but no type keyword → generic Zuruf
        # (only fires when canonicalize_party_list returned a known party,
        #  filtering out garbage strings that accidentally match _FACTION_PREP)
        nsc_type = "Zuruf"
    else:
        nsc_type = "unknown"

    content_text = speaker_info["content_text"] or faction_content

    party_canonical = "|".join(parties)
    return {
        "raw_segment":        segment,
        "nsc_type":           nsc_type,
        "qualifier":          qualifier,
        "speaker_name":       speaker_info["speaker_name"],
        "role":               speaker_info["role"],
        "title":              speaker_info["title"],
        "party_raw":          party_raw,
        "party_canonical":    party_canonical,
        "affiliation_derived": _derive_affiliation(speaker_info["role"], party_canonical),
        "content_text":       content_text,
        "is_named_speaker":   is_named,
        "is_faction_only":    bool(party_raw) and not is_named,
        "is_whole_house":     is_whole_house,
    }


def parse_row(row: pd.Series) -> list[dict]:
    """
    Parse one nsc row into 1..N segment dicts, each carrying the original
    row metadata plus segment_idx and n_segments.
    Expects v3 column names (paragraph_id, protocol_id, protocol_position, speech_id).
    """
    content = str(row["content"])
    state   = str(row.get("state", ""))
    cfg     = STATE_CONFIG.get(state, _DEFAULT_CFG)

    row_type = classify_row_type(content)
    text     = content.strip().lstrip("([").rstrip(")]").strip()

    base = {
        "paragraph_id":      row.get("paragraph_id", ""),
        "protocol_id":       row.get("protocol_id", ""),
        "speech_id":         row.get("speech_id", ""),
        "state":             state,
        "period":            row.get("period", ""),
        "nth":               row.get("nth", ""),
        "date":              row.get("date", ""),
        "protocol_position": row.get("protocol_position", ""),
        "raw_row":           content,
    }

    if row_type != "interjection":
        # For glocke rows, extract the presiding speaker if present
        glocke_speaker, glocke_role = "", ""
        if row_type == "glocke":
            gm = _GLOCKE_SPEAKER_RE.search(text)
            if gm:
                glocke_speaker = gm.group(1).strip()
                glocke_role    = "Präsident/in"
        return [{
            **base,
            "segment_idx":        0,
            "n_segments":         1,
            "raw_segment":        content,
            "nsc_type":           row_type,
            "qualifier":          "",
            "speaker_name":       glocke_speaker,
            "role":               glocke_role,
            "title":              "",
            "party_raw":          "",
            "party_canonical":    "",
            "affiliation_derived": _ROLE_TO_AFF.get(glocke_role, ""),
            "content_text":       "",
            "is_named_speaker":   bool(glocke_speaker),
            "is_faction_only":    False,
            "is_whole_house":     False,
        }]

    stripped   = strip_outer(content, cfg["outer"])
    normalized = normalize_ocr(stripped)
    segments   = validated_split(normalized, cfg["sep"])

    records = []
    n = len(segments)
    for i, seg in enumerate(segments):
        parsed = parse_segment(seg, cfg["fmt"])
        records.append({**base, "segment_idx": i, "n_segments": n, **parsed})
    return records


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Parse StateParl interjection rows")
    ap.add_argument("--state",  help="Process one state only (e.g. bb)")
    ap.add_argument("--sample", type=int, help="Random sample N rows (for testing)")
    args = ap.parse_args()

    data_root = get_data_root()
    src = data_root / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet"
    out = data_root / "processed" / "nsc.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading {src} ...")
    para = pd.read_parquet(src)
    nsc  = para[para["affiliation"] == "nsc"].copy()
    print(f"  {len(nsc):,} nsc rows across {nsc['state'].nunique()} states")

    if args.state:
        nsc = nsc[nsc["state"] == args.state]
        print(f"  Filtered to state={args.state}: {len(nsc):,} rows")

    if args.sample:
        nsc = nsc.sample(args.sample, random_state=42)
        print(f"  Sampled {len(nsc):,} rows")

    print("Parsing ...")
    records = []
    for _, row in nsc.iterrows():
        records.extend(parse_row(row))

    df = pd.DataFrame(records)
    df = df.sort_values(["state", "period", "nth", "protocol_position", "segment_idx"])
    df = df.reset_index(drop=True)

    # ── diagnostics ──────────────────────────────────────────────────────────
    print(f"\nOutput: {len(df):,} segments from {len(nsc):,} rows")
    print(f"Multi-segment rows: {(df['n_segments'] > 1).sum():,}")
    print()

    print("nsc_type breakdown (per source row, non-interjection types):")
    print(df.drop_duplicates("paragraph_id")["nsc_type"].value_counts().to_string())
    print()

    print("nsc_type breakdown (interjection rows only):")
    inj_df = df[~df["nsc_type"].isin(NON_INTERJECTION_TYPES)]
    print(inj_df["nsc_type"].value_counts().head(25).to_string())
    print()

    print("Unparsed rate by state (nsc_type == 'unknown', interjection rows only):")
    by_state = (
        inj_df.groupby("state")["nsc_type"]
        .apply(lambda x: (x == "unknown").mean())
        .sort_values(ascending=False)
    )
    print(by_state.apply(lambda x: f"{x:.1%}").to_string())
    print()

    print("Named-speaker rate by state (interjection rows only):")
    named_rate = (
        inj_df.groupby("state")["is_named_speaker"]
        .mean()
        .sort_values(ascending=False)
    )
    print(named_rate.apply(lambda x: f"{x:.1%}").to_string())

    df.to_parquet(out, index=False)
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
