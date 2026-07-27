# NSC pipeline cleanup for impoliteness classification — design

Date: 2026-07-27.

## Goal

Restructure the `nsc` (interjection) data pipeline so there is exactly one dataframe suited for
LLM impoliteness classification, fix the correctness bugs found while auditing it, and avoid
leaving more datasets/scripts lying around than the project actually needs. This supersedes part
of `docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md`'s Part 1 (the `nsc_llm.parquet`
join) for the classification path specifically — that spec's Part 2 (LLM scoring mechanics:
model, prompt, one-call-per-paragraph, seeding) is unaffected and still applies.

## Background: what prompted this

Auditing `nsc_llm.parquet` (built by `nsc_llm_explode.py`, consumed by
`impoliteness_pilot.ipynb`) surfaced several issues:

1. **Double-labeling risk**: `nsc_llm.parquet` explodes each segment on both `nsc_type` and
   `party_canonical` (pipe-joined multi-value fields → cross product). For classification, this
   means the same span of text (e.g. `"Beifall bei der SPD und der CDU"`) becomes two rows with
   identical `content_text`, which would get sent to the LLM and labeled twice.
2. **`content_text` blank-vs-NaN bug**: 29.2% of `nsc_llm` rows have `content_text == ""` (never
   true `NaN`), including 191,248 real `Zwischenruf` rows. The pilot notebook's
   `content_text.where(content_text.notna(), content)` fallback never fires for these, because
   `pd.notna("")` is `True` — so these rows would be sent to the LLM as empty strings instead of
   falling back to anything.
3. **`"Glocke"` exclusion bug**: `nsc_llm_explode.py`'s `_NON_INJ = {"glocke", "Prozedural",
   "mislabelled", "noise", "garbled"}` was meant to exclude non-interjection content, but
   `nsc_type` can independently hold the *capitalized* value `"Glocke"` (a chair's-bell reaction
   tag, distinct from the lowercase `"glocke"` row-type-level category, which is a full row that's
   *only* about the bell). Since `_NON_INJ` only lists lowercase `"glocke"`, `"Glocke"`-tagged rows
   (10,707 standalone + more in combos) were never excluded. Investigation showed this is actually
   **not** something to fix by excluding it — see Decision 5.

## Decisions

### 1. Regex/rule-based parsing stays; not ML

`nsc_rule_parser.py` already classifies >99% of the 4.2M `nsc` rows successfully (only 36,797
`unknown`, plus small `garbled`/`mislabelled`/`noise`/`Prozedural` counts). The bugs above are in
the *pipeline around* the parser, not evidence the regex approach is failing at extraction. This
reaffirms the decision already recorded in `measurement/PROGRESS.md`'s "ML classifier — decision:
NO" section. Revisit only if a specific, currently-unreachable distinction is needed (e.g.
reliably telling `Zwischenruf` from `Zuruf` in cases the parser currently can't).

### 2. Classification base = `nsc.parquet`, not `nsc_llm.parquet`

`nsc.parquet` (the rule-parser's direct output) already has multisegment splitting
(`segment_idx`/`n_segments`) but leaves `nsc_type`/`party_canonical` pipe-joined and unexploded —
exactly the granularity classification needs (one row per real segment of text, no
party-cross-product double-labeling). The party×type explosion in `nsc_llm_explode.py` is only
needed for the by-party time-series/crosstab analysis in `analysis/nsc_analysis.ipynb`.

**Action**: `nsc_llm_explode.py` → renamed `nsc_party_type_explode.py`; its output
`nsc_llm.parquet` → renamed `nsc_party_type.parquet`. Both names should signal "this is for
aggregate/crosstab analysis," not "this is what an LLM consumes." `analysis/nsc_analysis.ipynb`
updates its load path accordingly. `impoliteness_pilot.ipynb` stops using this file entirely for
the classification-input dataframe (see Decision 4).

### 3. `is_nsc` flag + corrected affiliation: a paragraph-level side table, not a modified `paragraphs.parquet`

`paragraphs.parquet` is the externally-sourced StateParl v3 release — not something this project
owns or regenerates, so it shouldn't be edited in place. New script (name TBD, e.g.
`measurement/nsc_paragraph_flags.py`) builds a small paragraph-level table:

- `paragraph_id`
- `is_nsc: bool` — `True` for every `paragraph_id` present in `nsc.parquet`'s interjection rows
  (mirrors `paragraphs.affiliation == "nsc"`, but as an explicit reusable flag rather than
  requiring every consumer to re-check the raw affiliation string)
- `affiliation_derived` — the properly-attributed party from parsing (already computed per-segment
  in `nsc.parquet`), so interjections get a real party attribution instead of the uninformative
  raw `"nsc"` affiliation code.

**Granularity choice**: this table is one row per `paragraph_id` (matching `paragraphs.parquet`'s
own grain), not one row per segment. For multi-segment paragraphs, `affiliation_derived` is taken
from `segment_idx == 0` (the first segment) as the representative value — a simplification for
this convenience layer. The full per-segment detail remains available in `nsc.parquet` itself for
anyone who needs it (e.g. the classification path). **Flagging this explicitly since it wasn't
separately confirmed**: please double check this first-segment convention is what you want when
you review this spec — an alternative would be one row per `(paragraph_id, segment_idx)`, but that
would fan out `paragraphs` joins for every consumer of this table, which seems like the wrong
default for a paragraph-level enrichment table.

Output: joinable onto `paragraphs.parquet` by `paragraph_id`, left-join, one row per paragraph.

### 4. Classification-input filtering: by content presence, not by type-name list

Rather than maintaining a hardcoded exclude-list of `nsc_type` strings (the root cause of the
`"Glocke"` bug — a list that silently drifted out of sync with real data values), the
classification-ready set is built by filtering `nsc.parquet`'s already-real-interjection rows
(row_type == interjection) down to those with **non-blank `content_text`**. This uniformly and
automatically drops `Beifall`/`Zustimmung`/`Heiterkeit`/`Lachen`/`Gelächter`/`Glocke` (98–100%
blank — there's no speech to judge tone of) without needing to name them individually.

**Known gap this creates, not solved by this redesign**: some genuinely content-bearing rows
(`Zwischenruf` especially — 191,248 rows, 11.7% of that type) also have blank `content_text` due
to parser extraction misses, not because nothing was said. These will also be excluded from the
classification input for now. We are **not** falling back to `raw_segment`/`raw_row` to recover
them (see Decision 6) — improving the parser's extraction coverage for these specific rows is a
separate future task, out of scope here.

**No new persisted file for this.** The classification-ready set is a runtime filter
(`row_type == "interjection"` — already implicit in `nsc.parquet` — and `content_text != ""`)
applied directly when `nsc.parquet` is loaded, not its own saved parquet. This avoids adding a
dataset that's just a filtered view of one that already exists.

### 5. `"Glocke"` is kept, not excluded — the earlier "bug" was accidentally correct behavior

Checked empirically: of 10,753 paragraphs containing a `Glocke` segment, 46.4% also contain an
`Unruhe` segment in the same paragraph (vs. ~1.7% base rate) — e.g. *"Zuruf von der SPD: Hören Sie
doch mal zu! – Glocke des Präsidenten"*, *"Unruhe im Hause – Glocke des Präsidenten – ... Die
Redezeit ist beendet!"*. This is the chair intervening in response to disorder — a real signal
close to the `Ordnungsruf` (chair-intervention) variable already planned in `CLAUDE.md`, not
noise to discard.

**Action**: `"Glocke"` (capitalized `nsc_type`) is *not* added to any exclusion list — it stays a
first-class, retained reaction-type in `nsc.parquet` and the aggregate dataset, exactly as it
already (accidentally) does today. It's excluded from the *classification* input only because it
has no text (Decision 4's content-presence filter), not because it's unwanted. **Update the
`_NON_INJ`-equivalent comment/docstring in the renamed aggregate-explode script to state this
retention is deliberate**, so a future reader doesn't "fix" it by excluding `Glocke`.

### 6. `content_text`, not `raw_segment`/`raw_row`, as the classifier's input text

`raw_segment`/`raw_row` still carry inline party attribution (e.g. *"Zuruf von der SPD: ..."*).
Showing this to the LLM risks a **party-priming confound**: since the research question is
whether AfD's presence causes more incivility, a model that has learned associations between
"AfD" and incivility from its own training data could rate text as more impolite *because* of the
visible party attribution, independent of actual tone — contaminating the outcome variable the
treatment effect depends on. `content_text` is already stripped of that attribution and is the
correct input for a "judge form/tone only" classifier. `raw_segment`/`raw_row` remain
parser-debugging/audit columns only.

### 7. Impoliteness judged per-segment in isolation; reactions kept as a separate, non-LLM variable

Reaction context (`Unruhe`, `Glocke`, `Beifall`, etc. following a segment) is not fed into the
classifier's prompt for a neighboring text-bearing segment, even though it's sequentially
meaningful (Decision 5). Rationale: if the audience's reaction were folded into the impoliteness
judgment itself, that judgment could no longer be compared *against* the reaction later — e.g.
"are impolite interjections increasingly met with no reprimand over time" requires the two to be
measured independently. The LLM judges only the isolated segment's words; reaction-type data
remains available for downstream analysis via the existing `paragraph_id`/`segment_idx`/
`protocol_position` ordering already in `nsc.parquet`, not as classifier input.

### 8. Row-type category renames

- `noise` → `document_reference` (or similar) — these are `Drucksache`/`Tagesordnungspunkt`/
  `Lesung` references, not garbage; they're just out of scope for interjection analysis. (Separate
  future idea, noted but not in scope here: detecting these same document references across the
  *whole* corpus, not just nsc rows, to eventually link paragraphs to their source
  bills/agenda items — tracked in memory, not this spec.)
- `mislabelled` → `misattributed` (or similar) — reflects that the *source data's*
  `affiliation == "nsc"` tag is wrong for these rows (they're actually chair remarks/narrative
  text), not that this pipeline mislabeled anything.

Exact final strings are Anna's call — flagged here for review rather than locked in, since this
is a naming/taste decision more than a technical one.

## What does NOT change

- `nsc_rule_parser.py`'s actual extraction logic (party/type/speaker parsing) — untouched, only the
  two row-type category *names* change.
- The multisegment-splitting behavior already in `nsc.parquet` — already correct, already what's
  needed.
- `impoliteness_pilot.ipynb` Part 2 (LLM scoring mechanics: model, prompt structure, one-call-per-
  paragraph, seeding) from the 2026-07-23 spec — unaffected by this redesign.

## File/script inventory after this change

| File | Role | Status |
|---|---|---|
| `measurement/nsc_rule_parser.py` | Parses `nsc` rows → `nsc.parquet` | Unchanged except category renames |
| `DATA_ROOT/processed/nsc.parquet` | Segment-level, multisegment-exploded, type/party NOT exploded | Unchanged shape; category renames flow through |
| `measurement/nsc_party_type_explode.py` (renamed from `nsc_llm_explode.py`) | Party×type cross-product for aggregate/crosstab analysis only | Renamed; doc comment clarifies `Glocke` retention is deliberate |
| `DATA_ROOT/processed/nsc_party_type.parquet` (renamed from `nsc_llm.parquet`) | Aggregate-analysis input | Renamed |
| `measurement/nsc_paragraph_flags.py` (new, name TBD) | Builds paragraph-level `is_nsc` + `affiliation_derived` side table | New |
| `DATA_ROOT/processed/nsc_paragraph_flags.parquet` (new, name TBD) | Joinable onto `paragraphs.parquet` | New |
| `measurement/impoliteness_pilot.ipynb` | Classification pipeline | Data-prep section rewritten to use `nsc.parquet` directly (content-presence filter), no `nsc_llm`/party-type join for classification |
| `analysis/nsc_analysis.ipynb` | Aggregate/crosstab/time-series analysis | Load path updated to `nsc_party_type.parquet` |

## Open items for Anna to confirm when reviewing this spec

1. First-segment-as-representative convention for `nsc_paragraph_flags` (Decision 3).
2. Exact renamed strings for `noise`/`mislabelled` categories (Decision 8).
3. Final file/script names (marked TBD above) — placeholders chosen for clarity, not precious.
