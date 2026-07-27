# Project progress & TODO

Last updated: 2026-07-27. Single project-wide tracking file — supersedes the old
`measurement/PROGRESS.md` (which only covered the parser). Kept as one file because tasks
across `preprocessing/`/`measurement/`/`analysis/`/`labelling/` are interrelated: some are
blocked on others, and finishing one often opens up or changes the next. Git history/commits
are authoritative for *what changed*; this file is for *what's open and why*, so nothing gets
lost between sessions.

## Status snapshot

Interjection parser (`preprocessing/nsc_rule_parser.py`) is mature — extensively audited
(see `analysis/nsc_analysis.ipynb`'s pre/post-processing audit cells), unknown-rate down to
~0.75% (36,268 of ~4.86M interjection segments), several rounds of confirmed bug fixes. The
nsc pipeline was restructured 2026-07-27 (see Decisions log) to separate ETL (`preprocessing/`)
from actual construct measurement (`measurement/`'s LLM impoliteness classifier), currently
mid-implementation. Labelling gold set (`labelling/annotations_output.csv`) still has only 36
rows, all `neutral` — not enough to validate any classifier yet.

## Ready now (unblocked)

- [ ] Run `preprocessing/nsc_rule_parser.py`, `preprocessing/nsc_party_type_explode.py`,
      `preprocessing/nsc_paragraph_flags.py` to regenerate parquet outputs after the
      2026-07-27 rename/restructure, and verify row counts/values against pre-restructure
      baselines.
- [ ] Validate `content_text` accuracy: sample against `raw_segment` for a stratified set
      (especially `Zwischenruf`) before trusting the classification-ready filter — see
      "Known limitations" below.
- [ ] Re-run `measurement/impoliteness_pilot.ipynb`'s LLM-scoring section against the
      rebuilt data-prep (now reads `nsc.parquet` directly, not `nsc_llm.parquet`).

## Blocked / needs a decision first

- **DiD / event-study analysis** — blocked on the impoliteness pilot actually producing
  validated scores; not started.
- **Validating the impoliteness classifier against gold labels** — blocked on the gold set
  containing positive (`unhöflich`) examples; currently all 36 labelled rows are `neutral`.
  Needs a targeted annotation pass (biased toward interjections / later periods).
- **Drucksache/Tagesordnungspunkt whole-corpus linkage** (see Ideas below) — blocked on
  deciding whether the referenced documents are even retrievable/scrapable; not scoped.

## Known limitations / open caveats

- **Party-priming confound (impoliteness classification, unresolved).** The classifier's
  input text (`content_text`) is stripped of inline party attribution so the model isn't told
  who said something before judging tone — this matters because the research question is
  whether AfD's presence causes *more* incivility, and a model with learned party/incivility
  associations from training data could rate text as more impolite based on attribution rather
  than actual tone. Decision (2026-07-27): proceed with labelling for the pilot anyway rather
  than block on solving this first, but revisit — e.g. compare impoliteness rates across
  parties on matched/neutral text once there's enough labelled data to check whether priming
  actually shows up empirically. See the nsc-pipeline-cleanup spec below.
- **`content_text` non-blank ≠ correct (unresolved).** Non-blank only means the parser
  extracted *something*, not that it's the *right* something. No accuracy check has been run
  yet against `raw_segment` for a stratified sample.
- **Coverage gap: blank `content_text` on real interjection rows.** ~11.7% of `Zwischenruf`
  rows (191,248) have blank `content_text` despite being genuine spoken content — a parser
  extraction miss, not "nothing was said." These are excluded from LLM classification input
  (not recovered via `raw_segment`/`raw_row`, to avoid the party-priming issue above) until
  parser coverage improves.

## Open parser-quality findings (from `analysis/nsc_analysis.ipynb`'s audit, not yet actioned)

Full detail and evidence lives in that notebook's markdown cells; summarized here so they
aren't only discoverable by reading the whole notebook:

- `_IS_MISATTRIBUTED` (renamed from `_IS_MISLABELLED`) anchor bug: `^`-anchored to row start,
  so narrative-aside content occurring as segment 2+ of a multi-segment row leaks into
  `unknown` instead of `misattributed`. Needs the pattern split into row-start-anchored vs.
  not-anchored alternatives — a real design decision, not a one-line fix.
- `colon_but_no_content`: 16,464 rows (0.34%) — clear `": spoken text"` in the source but no
  format regex matched, so the quote is dropped entirely. Long tail of one-off formats.
- BW bracket-format leakage: 2,666 rows (0.055%) use square-bracket party notation even
  though BW's format is nominally "space" — fallback matching leaves bracket residue in
  `speaker_name`/`content_text`.
- Bare attribution stubs (`"Vizepräsidentin Ries"`, `"Abg. Kemmerich"`) fabricate a
  zero-content `Zwischenruf` event — no reliable signal distinguishes a truncated stub from a
  legitimate bare attribution.
- `party_canonical == "OTHER"` conflates genuinely-unmapped entities with any remaining
  mechanical-failure share (currently 2.19% of interjections) — not a bug, but a labeling
  ambiguity worth remembering if `OTHER` is ever read as "minor party."
- ASCII-hyphen separator gap: `be/by/he/hh/mv/rp/sn/sl` only recognize the em-dash `–` as a
  segment separator, not the plain hyphen `-` — confirmed 3,879 rows (~0.08%) fail to split
  when source text uses a plain hyphen.

## Ideas / opportunities (parking lot — not scoped, not started)

- **Drucksache/Tagesordnungspunkt detection across the whole corpus** (flagged urgent by
  Anna, 2026-07-27): currently only detected within `nsc` rows (tagged `document_reference`,
  2,573 rows, excluded from interjection analysis) — but these document/agenda-item
  references appear throughout regular speech too. Goal: eventually scrape and match
  referenced documents to link paragraphs to the specific bill/agenda item being discussed.
  Related to the BB motion full-text extraction question below — likely the same underlying
  need.
- **BB motion full-text extraction** — decision pending, not started.
- **Project-level data-auditing skill**: turn the verification habits used in the 2026-07-27
  nsc-pipeline audit (check real dtype/blank-vs-NaN, verify exclusion filters against actual
  unique values with exact case, check co-occurrence/temporal evidence before writing off a
  category as noise, reconcile row-count arithmetic end-to-end) into a reusable
  `.claude/skills/` entry for this repo, so future sessions apply the same rigor by default.
  Not built yet.
- **`nsc_type` category critique adopted in `nsc_analysis.ipynb`**: merge `Zuruf`/`Zwischenruf`
  for analysis purposes and use `is_named_speaker` + non-empty `content_text` directly as the
  real attribution/completeness variables, since the type label is not a clean partition on
  either. Adopted in that notebook's own analysis cells; not a pipeline/parser change.

## Remaining pipeline stages (not yet started)

### Labelling (`labelling/`)

- [ ] Ordnungsruf detection (chair interventions — direct norm signal)
- [ ] Speech-type classification (question / reply / new topic)

### Analysis (`analysis/`)

- [ ] DiD / event study: AfD entry × interjection rate
- [ ] Party-specific response to AfD (who heckles, who applauds)
- [ ] Longitudinal norms: before/after AfD, by state and period
- [ ] Bundestag comparison (federal vs. state parliament norms)

### Data enrichment

- [ ] Link interjection `speaker_name` to StatePol `mandate_id` via mandates table (downstream join)
- [ ] Gender coding for speaker attributes

## Decisions log (pointers, not duplicated content)

- **2026-07-27 — nsc pipeline cleanup** (this restructure): classification base switched to
  `nsc.parquet` (not the party-exploded `nsc_llm.parquet`), folder split into
  `preprocessing/`/`measurement/`/`utils/`, row-type categories renamed
  (`noise`→`document_reference`, `mislabelled`→`misattributed`), `Glocke` confirmed as a
  deliberately-retained signal (not excluded). Full rationale:
  `docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md`.
- **2026-07-23/24 — impoliteness pilot design**: zero-shot LLM classifier (Qwen3, local
  Ollama), binary output, one call per paragraph, seeded for reproducibility. Full rationale:
  `docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md`.
- **2026-07-19 — regex vs. ML for interjection parsing: decided regex, not ML.** Interjections
  have explicit structural markers (`(...)`/`[...]`), unlike the soft-boundary speech
  segmentation the StateParl v3 paper uses ML for; regex is fully auditable for a thesis, no
  labeled training set exists, and the residual unknown rate is now ~0.75% — reaffirmed
  2026-07-27 during the nsc pipeline cleanup. Revisit only if a specific,
  currently-unreachable distinction becomes necessary.
