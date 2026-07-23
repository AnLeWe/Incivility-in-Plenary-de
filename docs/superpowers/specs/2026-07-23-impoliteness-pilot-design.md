# Impoliteness pilot — design

Date: 2026-07-23

## Goal

Build a zero-shot LLM classifier that scores paragraphs (regular speech + interjections) for
impoliteness, as an automated variable for the norm-erosion analysis. This is a **pilot**: it
proves out the method (prompt, model, output format) on a first sample. Validation against hand
labels (`labelling/annotations_output.csv`) is reserved for later, once the gold set contains
positive (`unhöflich`) examples — currently all 36 labeled rows are `neutral`, so no meaningful
validation is possible yet.

Scope is deliberately narrow: no fine-tuning (not enough gold data), no multi-dimension
classification (politeness only, not moral/justificatory civility), binary output
(impolite / not), 2021 data only for this first pass.

## Part 1: refresh script

New file: `labelling/refresh_annotation_inputs.py`

The existing annotation-input pools (`DATA_ROOT/labelling/annotations_input_{2010,2018,2021}_v3.csv`,
~600k rows each, all 16 states) still contain raw, unsplit `affiliation == "nsc"` rows —
predating `nsc_rule_parser.py`'s cleaned splitting/attribution. This script replaces those rows
with the cleaned, per-segment output now available in `DATA_ROOT/processed/nsc.parquet`.

**Logic**, per dataset:
1. Load the CSV and `nsc.parquet`.
2. Drop rows where `affiliation == "nsc"`.
3. From `nsc.parquet`, join in segments matching this dataset's `paragraph_id`s. Exclude
   non-utterance `nsc_type`s (`glocke`, `Prozedural`, `mislabelled`, `noise`, `garbled`) — same
   filter already used elsewhere in the pipeline (see `CLAUDE.md`). A single raw row can expand
   into multiple segment rows (multi-speaker interjections).
4. Use `content_text` (cleaned) as the new `content` field for these rows.
5. Concatenate with the untouched non-`nsc` rows (regular speech — unaffected, so none of the
   existing 36 gold labels break).

**Output**: new files, not overwrites — `annotations_input_{2010,2018,2021}_v3_nsc.csv` in the
same `DATA_ROOT/labelling/` directory. Keeps the raw pool around for reference.

Runs once per period; processes all 3 periods (2010/2018/2021) since looping over all three
costs nothing extra — even though the pilot notebook itself only uses 2021 for now.

## Part 2: `measurement/impoliteness_pilot.ipynb`

**Setup**: Colab notebook. Mount Drive for `DATA_ROOT` (same `IN_COLAB` pattern as
`explore_pol.ipynb`). Install `transformers accelerate bitsandbytes`. Load
`Qwen/Qwen2.5-14B-Instruct`, 4-bit quantized via bitsandbytes, `device_map="auto"` — works
whether Colab hands out a T4 or an A100.

**Data**: load `annotations_input_2021_v3_nsc.csv` only. Draw a random sample of size `N`
(notebook parameter, default e.g. 300) with a fixed random seed.

**Determinism**: everything seeded — the sampling seed, and generation itself (greedy decoding /
`do_sample=False`, plus `torch`/`transformers` seed set) so re-running the notebook on the same
input reproduces the same predictions.

**Prompt**: one paragraph per call (not batched — batching multiple paragraphs into one JSON-list
prompt risks the model dropping/merging items mid-batch, which would muddy quality assessment for
this first pilot). German system prompt adapted from `labelling/config.py`
`DEFINITIONS["politeness"]`, reframed as binary (unhöflich vs. not — the existing 3-class scheme
collapses `neutral`+`höflich` into "not impolite"). Model must return strict JSON:
`{"impolite": true/false, "reason": "<one sentence>"}`.

**Run loop**: iterate the sample, call the model, parse JSON. On unparseable output, flag the row
rather than crashing the run (e.g. `impolite = None`, raw output kept for inspection).

**Output**: `para_id, period, state, content, impolite, reason, model_name` saved to
`DATA_ROOT/measurement/impoliteness_pilot_predictions.csv`.

**Review section**: print predicted-impolite examples next to their source text for manual
sanity-checking; report predicted impoliteness rate overall and by state. Cross-check the 36 gold
`neutral` rows only as a rough false-positive signal (any of them predicted `impolite` flags a
prompt problem) — explicitly provisional, not real validation.

## Explicitly out of scope (for now)

- Fine-tuning any model
- Multi-dimension classification (moral/justificatory civility)
- 2010/2018 data in the pilot notebook itself (refresh script prepares them, notebook doesn't use
  them yet)
- Batched/multi-paragraph prompting
- Full-corpus scale run and its cost/throughput trade-offs (API vs. local model) — revisit once
  the pilot's quality and Colab throughput are known
- Expanding the gold-label set — noted as a real gap (zero positive examples currently) but
  deferred; may need a targeted annotation pass later to enable real validation
