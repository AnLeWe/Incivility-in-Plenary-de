# Preprocessing — nsc (interjection) ETL

Three scripts, run in this order, each reading the previous one's output:

1. **`nsc_rule_parser.py`** — parses raw `affiliation == "nsc"` rows from
   `stateparl_v3_paragraphs.parquet` into structured segments: row-type classification
   (`document_reference`/`Prozedural`/`misattributed`/`garbled`/`glocke`/`interjection`),
   multisegment splitting, type/speaker/party extraction, party canonicalization. Output:
   `nsc.parquet` — one row per segment, `nsc_type`/`party_canonical` left pipe-joined for
   multi-value cases (not yet exploded). Exports `NON_INTERJECTION_TYPES`, the single source
   of truth for excluding non-reaction categories — import it rather than re-hardcoding the
   set.

2. **`nsc_party_type_explode.py`** — explodes `nsc.parquet`'s pipe-joined `nsc_type`/
   `party_canonical` into one row per (segment, type, party) atomic unit. Output:
   `nsc_party_type.parquet`. Only needed for the by-party/by-type crosstab and time-series
   analysis in `analysis/nsc_analysis.ipynb` — not used for LLM impoliteness classification,
   since exploding on party would double-label the same span of text once per attributed
   party.

3. **`nsc_paragraph_flags.py`** — builds a small paragraph-level side table (`is_nsc` boolean
   + a properly-attributed `affiliation_derived`), joinable onto
   `stateparl_v3_paragraphs.parquet` by `paragraph_id`. Doesn't modify `paragraphs.parquet`
   itself — that's the externally-sourced StateParl release.

Full design rationale for this three-script split (and the categories/naming above):
`docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md`.

For the detailed parsing rules — state-specific formats, party-canonicalization patterns,
full output schema, known limitations — see `nsc_rule_parser.py`'s own module docstring and
source directly. This file used to carry a long, separate deep-dive on all of that, written
against StateParl v2; it went stale across the v2→v3 migration and the 2026-07-27 category
renames, so it's been replaced with this short overview rather than maintained as a second,
drifting copy of what the code itself already says.
