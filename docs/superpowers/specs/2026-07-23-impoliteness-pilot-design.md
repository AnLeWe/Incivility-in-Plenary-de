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
5. **Mint a unique `paragraph_id` for split segments**: `annotator_app.py` treats `para_id` as a
   unique key (`drop_duplicates(subset="para_id")`, a `coded_ids` set used to skip already-
   annotated rows). A multi-speaker interjection row expands into several segment rows that would
   otherwise all share the same original `paragraph_id` — annotating one would silently mark all
   its siblings as already-coded. Fix: keep `paragraph_id` unchanged when `n_segments == 1`; use
   `f"{paragraph_id}_s{segment_idx}"` when `n_segments > 1`.
6. Concatenate with the untouched non-`nsc` rows (regular speech — unaffected, so none of the
   existing 36 gold labels break).

**Output**: new files, not overwrites — `annotations_input_{2010,2018,2021}_v3_nsc.csv` in the
same `DATA_ROOT/labelling/` directory. Keeps the raw pool around for reference.

Runs once per period; processes all 3 periods (2010/2018/2021) since looping over all three
costs nothing extra — even though the pilot notebook itself only uses 2021 for now.

## Part 2: `measurement/impoliteness_pilot.ipynb`

**Setup**: local Mac (32GB unified memory), via Ollama — no Colab needed. `DATA_ROOT` read from
`.env` (same local-fallback path already in the notebook's setup cell). Run `ollama pull
qwen3:14b-fp16` and call it via the `ollama` Python client (`ollama.chat(...)`), rather than
`transformers`/`bitsandbytes` (bitsandbytes 4-bit is CUDA-only and doesn't work on Apple Silicon
anyway). fp16 Qwen3-14B is ~30GB of weights alone — tight against 32GB shared with macOS itself,
real risk of memory pressure/swapping. Fallback if that happens: `ollama pull qwen3:14b-q8_0`
(~15GB, still much better quality than Q4) — a one-line model-tag swap, no code change. Qwen3 has
a "thinking mode" that must be explicitly disabled (pass `think: false` in the Ollama request, or
prefix the prompt with `/no_think`) — otherwise it emits chain-of-thought before the JSON answer,
which breaks the strict-JSON parsing below.

**Data**: load `annotations_input_2021_v3_nsc.csv` only. Draw a random sample of size `N`
(notebook parameter, default e.g. 300) with a fixed random seed.

**Determinism**: everything seeded — the sampling seed, and generation itself (`temperature: 0`
and a fixed `seed` in the Ollama request options) so re-running the notebook on the same input
reproduces the same predictions.

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

## Future work: Phase 2 model comparison

Once this pilot's quality and Colab throughput are known, compare accuracy/cost across:

- **Best open-weights, high accuracy**: `meta-llama/Llama-3.3-70B-Instruct` — 70B, needs Q4 even
  on an A100; candidate for best raw quality on European-language / regional-dialect nuance.
- **Best efficiency/cost**: `Qwen/Qwen3-14B` — the model this pilot already uses (note: the
  model's real Hub ID has no `-Instruct` suffix; Qwen3 ships instruction-tuned under the plain
  name, unlike Qwen2.5).
- **Best proprietary**: whatever the current best Claude model is at the time this phase runs
  (Anthropic's lineup moves — as of this pilot's design date the current models are Sonnet 5 /
  Opus 4.8 / Haiku 4.5, not "Claude 4.5"; re-check before committing to a specific model ID).

Not designed yet — brainstorm as its own thing when the pilot is done.

## Future work: Phase 3 distillation to a production encoder

Teacher–student pattern to make full-corpus scoring (16M paragraphs / 4.2M interjection rows)
cheap enough to actually run, instead of calling a 14B/70B LLM per row:

1. **One-time/batch**: run the chosen teacher LLM (from Phase 2) zero-shot over a larger batch
   (e.g. 50,000 paragraphs) to generate silver (LLM-predicted, not hand-verified) impoliteness
   labels — same method as this pilot, larger N.
2. **Production/streaming**: fine-tune a small encoder-only model on those silver labels; that
   model does the actual full-corpus scoring cheaply.

Candidate student model: `LSX-UniWue/ModernGBERT_1B` (or the smaller `134M` variant) — a
German-native ModernBERT architecture from Würzburg. Notably, `schlenker/moderngbert-parl-german-
stance-detection` already exists on the Hub as a ModernGBERT model fine-tuned on German
parliamentary stance data, i.e. a proven-fit precedent for this exact domain.

Caveat: quality is bounded by the teacher LLM's zero-shot accuracy — errors/biases in step 1
propagate into the student's training data. Treat these as silver labels, not gold; spot-check
the student's predictions against real hand labels once the gold set (currently all-`neutral`)
has positive examples.

Not designed yet — brainstorm as its own thing once Phase 2 is done.
