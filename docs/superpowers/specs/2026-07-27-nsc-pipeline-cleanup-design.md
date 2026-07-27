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
   *only* about the bell). **This is not a regex case-sensitivity bug** — the regex that assigns
   the lowercase row-type category (`_IS_GLOCKE = re.compile(r'\bglocke\w*\b', re.I)`) already has
   `re.I`. `_NON_INJ` is checked via plain Python `set` membership (`nsc_type.isin(_NON_INJ)`) —
   exact string equality, not text search — against `nsc.parquet`'s `nsc_type` column, which
   genuinely contains both `"glocke"` and `"Glocke"` as two intentionally distinct values (the
   former assigned by `classify_row_type()` *before* extraction runs, for rows that are only ever
   about the bell; the latter assigned *after* full extraction, as a reaction-type tag that can
   coexist with `Zuruf`/`Unruhe`/etc. via the pipe-join). Nobody had explicitly decided what to do
   with the capitalized one — it simply wasn't in the set. Investigation showed this is actually
   **not** something to fix by excluding it — see Decision 5.
4. **`nsc.parquet` is not pre-filtered to interjection rows.** It contains all `nsc`-affiliated
   rows, including `"glocke"`, `"noise"`, `"Prozedural"`, `"mislabelled"` as literal `nsc_type`
   values — there is no separate `row_type` column anywhere in its schema. The *only* place the
   non-interjection exclusion currently happens is `_NON_INJ` inside `nsc_llm_explode.py`, which
   this redesign moves away from as the classification base — see Decision 4's correction below.

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
classification-ready set is built by filtering `nsc.parquet` down to those rows with
**non-blank `content_text`**. **Correction from the first draft of this spec**: since
`nsc.parquet` itself is *not* pre-filtered (see Background point 4), this still requires
explicitly excluding the renamed non-interjection categories (`document_reference`/`Prozedural`/
`misattributed`/`garbled`, plus row-type-level `glocke`) first — the content-presence filter
alone isn't sufficient, because e.g. a `document_reference`/`Prozedural` row could coincidentally
have non-blank text that isn't a real reaction. The corrected two-step filter: (1) exclude the
non-interjection `nsc_type` categories (same exclusion `nsc_llm_explode.py`/
`nsc_party_type_explode.py` already does, just re-applied directly against `nsc.parquet` instead
of relying on the renamed script), then (2) within what's left, keep only non-blank `content_text`
— which is what correctly and automatically drops `Beifall`/`Zustimmung`/`Heiterkeit`/`Lachen`/
`Gelächter`/`Glocke` (98–100% blank — there's no speech to judge tone of) without needing to name
them individually.

**Before trusting non-blank `content_text` as correct**: non-blank only means the parser
extracted *something*, not that it's the *right* something. Add a validation step before mass
classification — sample `content_text` against `raw_segment` for a stratified set (especially
`Zwischenruf`, the category the classifier depends on most) and estimate an actual
extraction-accuracy rate, rather than assuming non-blank rows are clean.

**Known gap this creates, not solved by this redesign**: some genuinely content-bearing rows
(`Zwischenruf` especially — 191,248 rows, 11.7% of that type) also have blank `content_text` due
to parser extraction misses, not because nothing was said. These will also be excluded from the
classification input for now. We are **not** falling back to `raw_segment`/`raw_row` to recover
them (see Decision 6) — improving the parser's extraction coverage for these specific rows is a
separate future task, out of scope here.

**No new persisted file for this.** The classification-ready set is a runtime filter (exclude
non-interjection categories, then `content_text != ""`) applied directly when `nsc.parquet` is
loaded, not its own saved parquet. This avoids adding a dataset that's just a filtered view of one
that already exists.

**Implementation-time bug found and fixed (2026-07-27), same failure family as the original
blank-vs-NaN issue**: excluding non-interjection categories from `nsc` *before* the join (rather
than after, as the old `nsc_llm` pipeline did) means some paragraphs' entire nsc entry gets
excluded — every one of their segments was e.g. `document_reference`/`misattributed` — so the
left join produces no match at all for that `paragraph_id`, and `text_to_classify` ends up `None`
rather than `""`. A plain `!= ""` filter treats `None` as "not blank" (`None != ""` is `True` in
pandas), so it silently let one such row (`paragraph_id` 11554984, confirmed via end-to-end
verification against real data) through into a test sample with an empty prompt. Fixed by
requiring `.notna()` explicitly alongside `!= ""` in `impoliteness_pilot.ipynb`'s sampling cell.
Caught ~6,800 additional rows the naive check had been missing, on top of the ~126k already
correctly excluded.

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
  future idea, must urgently be added to the projects TODO list, but not in scope here:
  detecting these same document references like Drucksache that give context for the current debate across the
  *whole* corpus, not just nsc rows, to eventually link paragraphs to their source
  bills/agenda items — tracked in memory, not this spec.)
- `mislabelled` → `misattributed` (or similar) — reflects that the *source data's*
  `affiliation == "nsc"` tag is wrong for these rows (they're actually chair remarks/narrative
  text), not that this pipeline mislabeled anything.

Exact final strings are Anna's call — flagged here for review rather than locked in, since this
is a naming/taste decision more than a technical one.

### 9. Folder restructure: `preprocessing/` for ETL, `measurement/` narrowed to actual scoring

Once the classification/aggregate split above was settled, it became clear the *files*
implementing it were misplaced: `measurement/` was holding both ETL scripts (parsing/exploding
nsc rows) and the actual construct-measurement code (the LLM impoliteness classifier), which
`CLAUDE.md` itself conflated under one "Measurement Pipeline" heading. Decided:

- **New top-level `preprocessing/` folder** holds the ETL layer: `nsc_rule_parser.py`,
  `nsc_party_type_explode.py` (renamed per Decision 2), `nsc_paragraph_flags.py` (new, per
  Decision 3), `interjections_pipeline.md`.
- **`measurement/` narrows to just the actual scoring code**: `impoliteness_pilot.ipynb`,
  `impoliteness_lib.py`, `test_impoliteness_lib.py`.
- **`colors.py`/`colors.R` move to a new top-level `utils/` folder**, not `analysis/` — per
  Anna: "colors should be used for the whole project, it is the project's colors," i.e.
  project-wide shared constants, not scoped to any one pipeline stage. Both `preprocessing/`
  and `utils/` get an `__init__.py` so package-style imports (`from utils.colors import ...`,
  `from preprocessing.nsc_rule_parser import ...`) work the same way `measurement/__init__.py`
  already enabled for `colors.py`.
- **Consequences handled**: `.githooks/pre-commit`'s requirements-regeneration trigger extended
  to watch `preprocessing/` and `utils/` too; `analysis/nsc_analysis.ipynb` and
  `analysis/nsc_ml_extraction.ipynb`'s import paths and markdown references updated
  (`from measurement.colors import ...` → `from utils.colors import ...`,
  `measurement/nsc_rule_parser.py` → `preprocessing/nsc_rule_parser.py`); `nsc_analysis.ipynb`'s
  own hardcoded `_NON_INJ` set (a 4th copy of the same exclusion list, found during this
  restructure) replaced with an import of `nsc_rule_parser.NON_INTERJECTION_TYPES`, the single
  source of truth now exported from that module.

### 10. Single project-wide `PROGRESS.md`, not one per folder

Anna: "I need one general todo list. Things will accumulate, and they will be interrelated...
I need a dynamic todo file or progress that shows where we are actually going." Decided against
a per-folder progress file (the old `measurement/PROGRESS.md` only covered the parser) in favor
of one root-level `PROGRESS.md` covering `preprocessing/`/`measurement/`/`analysis/`/
`labelling/` together, structured as: status snapshot, ready-now, blocked/needs-a-decision,
known limitations, open parser-quality findings (surfaced from `nsc_analysis.ipynb`'s audit
cells, which aren't otherwise centrally tracked), an ideas/opportunities parking lot, remaining
pipeline stages, and a decisions log pointing to specs rather than duplicating them. Kept
deliberately lightweight (plain markdown, no new tooling) per Anna's explicit "I do not have
time for that right now" re: a more elaborate solution.

## What does NOT change

- `nsc_rule_parser.py`'s actual extraction logic (party/type/speaker parsing) — untouched, only the
  two row-type category *names* change.
- The multisegment-splitting behavior already in `nsc.parquet` — already correct, already what's
  needed.
- `impoliteness_pilot.ipynb` Part 2 (LLM scoring mechanics: model, prompt structure, one-call-per-
  paragraph, seeding) from the 2026-07-23 spec — unaffected by this redesign.

## File/script inventory after this change (final — implemented and verified 2026-07-27)

| File | Role | Status |
| --- | --- | --- |
| `preprocessing/nsc_rule_parser.py` (moved from `measurement/`) | Parses `nsc` rows → `nsc.parquet` | Category renames applied; exports `NON_INTERJECTION_TYPES` as the single source of truth (was duplicated across 4 files) |
| `DATA_ROOT/processed/nsc.parquet` | Segment-level, multisegment-exploded, type/party NOT exploded | Regenerated; row count unchanged at 4,920,872, category counts verified identical to pre-restructure baseline |
| `preprocessing/nsc_party_type_explode.py` (moved + renamed from `measurement/nsc_llm_explode.py`) | Party×type cross-product for aggregate/crosstab analysis only | Doc comment clarifies `Glocke` retention is deliberate; imports `NON_INTERJECTION_TYPES` instead of a local copy |
| `DATA_ROOT/processed/nsc_party_type.parquet` (renamed from `nsc_llm.parquet`) | Aggregate-analysis input | Regenerated; byte-identical size to old `nsc_llm.parquet` confirms no behavior change; old file removed |
| `preprocessing/nsc_paragraph_flags.py` | Builds paragraph-level `is_nsc` + `affiliation_derived` side table | New; verified 4,207,561 rows = exactly `paragraphs.affiliation == "nsc"` count |
| `DATA_ROOT/processed/nsc_paragraph_flags.parquet` | Joinable onto `paragraphs.parquet` | New |
| `measurement/impoliteness_pilot.ipynb` | Classification pipeline | Data-prep section rewritten to use `nsc.parquet` directly, no `nsc_llm`/party-type join; NaN-vs-blank bug found and fixed (see Decision 4) |
| `analysis/nsc_analysis.ipynb` | Aggregate/crosstab/time-series analysis | Import paths updated (`utils.colors`, `preprocessing.nsc_rule_parser`); own hardcoded `_NON_INJ` replaced with `NON_INTERJECTION_TYPES` import |
| `analysis/nsc_ml_extraction.ipynb` | Stub, ML enrichment (not yet built) | Path references updated only |
| `utils/colors.py` / `utils/colors.R` (moved from `measurement/`) | Project-wide color constants | Moved per Decision 9 |
| `PROGRESS.md` (new, repo root; superseded `measurement/PROGRESS.md`) | Single project-wide TODO/status | New, per Decision 10 |
| `.githooks/pre-commit` | Requirements-regeneration trigger | Extended to watch `preprocessing/` and `utils/` |
| `CLAUDE.md` | Project documentation | Repository-layout section added; Measurement Pipeline section split into preprocessing vs. measurement |

## Open items — resolved

1. First-segment-as-representative convention for `nsc_paragraph_flags` (Decision 3) — kept as
   proposed, no objection raised.
2. Renamed category strings (Decision 8) — `document_reference`/`misattributed` confirmed via
   implementation, no alternative requested.
3. Folder/file names — `preprocessing/` (not `prep/`), `utils/` for colors, `nsc_paragraph_flags.py`
   — all confirmed by Anna during implementation.
