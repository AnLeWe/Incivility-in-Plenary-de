# Impoliteness pilot — design

Date: 2026-07-23. Revised 2026-07-24 (Part 1 rewritten to match already-built work).

## Goal

Build a zero-shot LLM classifier that scores paragraphs (regular speech + interjections) for
impoliteness, as an automated variable for the norm-erosion analysis. This is a **pilot**: it
proves out the method (prompt, model, output format) on a first sample. Validation against hand
labels (`labelling/annotations_output.csv`) is reserved for later, once the gold set contains
positive (`unhöflich`) examples — currently all 36 labeled rows are `neutral`, so no meaningful
validation is possible yet.

Scope is deliberately narrow: no fine-tuning (not enough gold data), no multi-dimension
classification (politeness only, not moral/justificatory civility), binary output
(impolite / not).

## Part 1: data preparation (already built, 2026-07-24)

This part was built directly by Anna in parallel with this spec, not planned here — documented
for completeness so the rest of the spec makes sense. Supersedes the original Part 1 plan (a
`labelling/refresh_annotation_inputs.py` script targeting the annotator's CSV pool) with a more
general and better-motivated approach: sampling straight from the master paragraphs table within
a research-relevant event window, instead of the fixed-year annotator CSVs.

**`measurement/nsc_llm_explode.py`** (new script): explodes `nsc.parquet` into one row per
`(nsc_type, party_canonical)` atomic unit — the shape an LLM text classifier needs, since a single
parsed segment can carry multiple pipe-joined types (`"Heiterkeit|Beifall"`) and/or multiple
pipe-joined parties (`"CDU|SPD"`). Multi-type and multi-party rows are exploded independently in
sequence, which produces their cross-product for the rare (~0.45%) segments with both. Rows with
neither multiplicity (the large majority) pass through unchanged. Non-interjection `nsc_type`s
(`glocke`, `Prozedural`, `mislabelled`, `noise`, `garbled`) are excluded, matching the filter used
elsewhere in the pipeline. Output: `DATA_ROOT/processed/nsc_llm.parquet` (6,176,081 rows from
4,112,535 distinct source paragraphs, as of the 2026-07-24 run).

**`measurement/impoliteness_pilot.ipynb`, data-prep section** (already written and executed):

1. Load `stateparl_v3_paragraphs.parquet` (16,078,467 rows, all 16 states) and `nsc_llm.parquet`.
2. Derive each state's AfD entry date from the corpus itself: the first legislative period with
   any `affiliation == "afd"` row, using that period's own constitutive-session date (first
   sitting overall) — the same corpus-derived method already validated in
   `analysis/nsc_analysis.ipynb`'s `AFD_PRESENCE` derivation. Produces `AFD_ENTRY: dict[state,
   Timestamp]`, one date per state (all 16 resolved).
3. Filter `paragraphs` to a **±1 year window around each state's own AfD entry date** — a
   per-state event window, not a single shared calendar year. Result: 1,223,597 of 16,078,467
   paragraphs (7.6%), all 16 states represented.
4. Left-join `nsc_llm` onto the windowed paragraphs on `paragraph_id` (dropping `nsc_llm` columns
   that duplicate `paragraphs` columns first: `protocol_id`, `speech_id`, `state`, `period`,
   `nth`, `date`, `protocol_position`, `raw_row`). Non-`nsc` paragraphs get exactly one output row
   (all `nsc_llm` columns `NaN`); `nsc`-affiliated paragraphs fan out to one row per matching
   `nsc_llm` classification unit. Result: `merged`, 1,399,244 rows.

This is the actual current state — **verify it's still current by checking the notebook and
`DATA_ROOT/processed/nsc_llm.parquet` directly before building on it**, since it was built outside
this spec's tracked history.

## Part 2: `measurement/impoliteness_pilot.ipynb`, LLM-scoring section (to build)

**Data**: sample from `merged` (Part 1's output) — all 16 states, each within its own AfD-entry
±1yr window — rather than a single fixed year. Draw a random sample of size `N` (notebook
parameter, default e.g. 300) with a fixed random seed. For rows where `nsc_llm` columns are
present (interjections), classify `content_text`; for rows where they're `NaN` (regular speech),
classify `content`.

**Setup**: local Mac (32GB unified memory), via Ollama — no Colab needed. `DATA_ROOT` read from
`.env` (same local-fallback path already in the notebook's setup cell). Call the model via the
`ollama` Python client (`ollama.chat(...)`), rather than `transformers`/`bitsandbytes`
(bitsandbytes 4-bit is CUDA-only and doesn't work on Apple Silicon anyway). Qwen3 has a "thinking
mode" that must be explicitly disabled (`think=False` in the `ollama.chat` call) — otherwise it
emits chain-of-thought before the JSON answer, which breaks the strict-JSON parsing below.

**Model tag — downgraded twice in practice, both times for real observed reasons, not
speculative caution:**

1. `qwen3:14b-fp16` (~30GB) — original plan. Never pulled: the actual network connection turned
   out too slow (~3 MB/s, 2+ hour ETA), so this was abandoned before completion in favor of (2).
2. `qwen3:14b-q8_0` (~15GB) — used successfully for Task 2 (model pull, sampling, smoke test all
   verified working). Failed in Task 3: reloading this model mid-run (Ollama unloads an idle
   model between cells, then reloads it) crashed the Jupyter kernel (`nbclient.exceptions.
   DeadKernelError`) under real, measured memory pressure — at the failure timestamp, Ollama's own
   server log showed ~5-7GB free RAM and 0 free swap; independently confirmed days later via
   `vm_stat`/`sysctl vm.swapusage` still showing ~64-77MB free RAM and ~1.5GB free swap, driven by
   many unrelated resident apps (browser, IDE, antivirus agent, etc.), not by the notebook itself.
3. `qwen3:14b-q4_K_M` (exact Hub tag confirmed via `ollama.com/library/qwen3/tags`) — current
   choice, ~7-8GB, chosen specifically to survive the same chronic memory pressure rather than
   requiring the user to close other applications first.

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

**Output**: `paragraph_id, state, period, date, affiliation, content, impolite, reason,
model_name` saved to `DATA_ROOT/measurement/impoliteness_pilot_predictions.csv`.
`paragraph_id` here is `merged`'s own column — unlike the abandoned refresh-script plan, it's
never renamed/suffixed, so it lines up directly with `labelling/annotations_output.csv`'s
`para_id` for the gold-label cross-check below with no ID translation needed.

**Review section**: print predicted-impolite examples next to their source text for manual
sanity-checking; report predicted impoliteness rate overall and by state. Cross-check the 36 gold
`neutral` rows only as a rough false-positive signal (any of them predicted `impolite` flags a
prompt problem) — explicitly provisional, not real validation.

## Explicitly out of scope (for now)

- Fine-tuning any model
- Multi-dimension classification (moral/justificatory civility)
- Batched/multi-paragraph prompting
- Full-corpus scale run and its cost/throughput trade-offs (API vs. local model) — revisit once
  the pilot's quality is known (see Phase 3 below)
- Expanding the gold-label set — noted as a real gap (zero positive examples currently) but
  deferred; may need a targeted annotation pass later to enable real validation

## Future work: Phase 2 model comparison

Once this pilot's quality and local Mac throughput are known, compare accuracy/cost across:

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
