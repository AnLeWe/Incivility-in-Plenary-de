# Impoliteness Pilot — LLM Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the LLM-scoring section to `measurement/impoliteness_pilot.ipynb` — sample paragraphs
from the already-built `merged` dataset, classify each for impoliteness with a local Qwen3-14B
model via Ollama, and save/review the predictions.

**Architecture:** A small testable library module (`measurement/impoliteness_lib.py`) holds the
two pure functions that matter for correctness — prompt construction and response parsing — so
they get real unit tests. The notebook itself stays exploratory/interactive (matching this repo's
existing convention: diagnostic printouts + manual sample review, no pytest on notebook cells) and
just wires that library together with sampling, the Ollama call loop, and a review section.

**Tech Stack:** Python, pandas, the `ollama` PyPI package (calling a local Ollama server), pytest.

## Global Constraints

- Model: `qwen3:14b-fp16` via Ollama (fallback `qwen3:14b-q8_0` if memory pressure) — see spec
  `docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md`.
- Qwen3's thinking mode must be disabled (`think=False` in the `ollama.chat` call) or the raw
  response contains chain-of-thought text before the JSON and breaks parsing.
- Every generation call must be deterministic: `temperature: 0` and a fixed `seed` in `options`.
- Every `ollama.chat` call passes `format="json"` — this constrains decoding to valid JSON at the
  model level (verified present in the installed `ollama` 0.6.2 package's `chat()` signature),
  not just a prompt instruction hoping for compliance, which is why `parse_response`'s
  "unparseable" branch (Task 1) should be rare in practice.
- One paragraph per `ollama.chat` call — no batching multiple paragraphs into one prompt.
- Binary output only: `{"impolite": true/false, "reason": "<one sentence>"}` — no 3-class scheme.
- Sample from `merged` (built in the notebook's existing data-prep section — all 16 states, each
  within its own AfD-entry ±1yr window), not a fixed year or the annotator CSVs.
- No fine-tuning, no multi-dimension (moral/justificatory) classification, no full-corpus run —
  this is a pilot on a few hundred rows.

---

### Task 1: `impoliteness_lib.py` — prompt building and response parsing

**Files:**
- Create: `measurement/impoliteness_lib.py`
- Test: `measurement/test_impoliteness_lib.py`

**Interfaces:**
- Produces: `SYSTEM_PROMPT: str`, `build_prompt(text: str) -> list[dict]`,
  `parse_response(raw: str) -> dict` with keys `impolite` (`bool | None`), `reason` (`str | None`),
  `raw_output` (`str`). These are imported directly by the notebook in Task 2/3 (`from
  impoliteness_lib import build_prompt, parse_response`).

- [ ] **Step 1: Install pytest and the ollama package into the project's venv**

Run: `norm_env/bin/python -m pip install pytest ollama`
Expected: both install successfully (neither was previously installed — verified via
`norm_env/bin/python -m pip list` showing no `pytest` or `ollama` entries).

- [ ] **Step 2: Write the failing tests**

Create `measurement/test_impoliteness_lib.py`:

```python
import json

from impoliteness_lib import SYSTEM_PROMPT, build_prompt, parse_response


def test_build_prompt_includes_system_and_user_message():
    messages = build_prompt("Das ist eine Frechheit!")

    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "Das ist eine Frechheit!"}


def test_parse_response_valid_impolite():
    raw = json.dumps({"impolite": True, "reason": "Beleidigung."})

    result = parse_response(raw)

    assert result == {"impolite": True, "reason": "Beleidigung.", "raw_output": raw}


def test_parse_response_valid_not_impolite():
    raw = json.dumps({"impolite": False, "reason": "Sachlicher Beitrag."})

    result = parse_response(raw)

    assert result["impolite"] is False
    assert result["reason"] == "Sachlicher Beitrag."


def test_parse_response_malformed_json_is_flagged_not_raised():
    raw = "Das ist unhöflich, würde ich sagen."

    result = parse_response(raw)

    assert result["impolite"] is None
    assert result["raw_output"] == raw


def test_parse_response_missing_impolite_key_is_flagged():
    raw = json.dumps({"reason": "kein impolite-Feld"})

    result = parse_response(raw)

    assert result["impolite"] is None


def test_parse_response_non_bool_impolite_is_flagged():
    raw = json.dumps({"impolite": "true", "reason": "String statt bool"})

    result = parse_response(raw)

    assert result["impolite"] is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd measurement && ../norm_env/bin/python -m pytest test_impoliteness_lib.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'impoliteness_lib'`

- [ ] **Step 4: Write the implementation**

Create `measurement/impoliteness_lib.py`:

```python
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

    impolite = parsed.get("impolite")
    if not isinstance(impolite, bool):
        return {"impolite": None, "reason": None, "raw_output": raw}

    reason = parsed.get("reason")
    if not isinstance(reason, str):
        reason = None

    return {"impolite": impolite, "reason": reason, "raw_output": raw}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd measurement && ../norm_env/bin/python -m pytest test_impoliteness_lib.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add measurement/impoliteness_lib.py measurement/test_impoliteness_lib.py
git commit -m "Add prompt/response-parsing library for impoliteness pilot"
```

---

### Task 2: Ollama model setup and sampling cell

**Files:**
- Modify: `measurement/impoliteness_pilot.ipynb` (append cells after the existing data-prep
  section — last existing cell has id `fbf6c1b4`, the sanity-check preview cell)

**Interfaces:**
- Consumes: `merged` (DataFrame, from the notebook's existing data-prep section — columns include
  `paragraph_id`, `state`, `period`, `date`, `affiliation`, `content`, `content_text`,
  `segment_idx`), `impoliteness_lib.build_prompt`/`parse_response` (Task 1).
- Produces: `sample` (DataFrame, columns: `paragraph_id`, `state`, `period`, `date`,
  `affiliation`, `text_to_classify`, plus all other `merged` columns) and `MODEL: str`, `SEED:
  int`, both consumed by Task 3.

- [ ] **Step 1: Check Ollama is installed and has enough disk space**

Run: `ollama --version && df -h / | tail -1`
Expected: a version string (e.g. `ollama version is 0.32.1`) and at least 35GB available
(`qwen3:14b-fp16` is ~30GB).

- [ ] **Step 2: Add a markdown cell introducing the LLM-scoring section**

Append a markdown cell:

```markdown
## LLM scoring — zero-shot impoliteness classification

Sample paragraphs from `merged` and classify each with a local Qwen3-14B model via Ollama.
See `docs/superpowers/specs/2026-07-23-impoliteness-pilot-design.md` (Part 2) for the design
rationale: binary output, one call per paragraph, everything seeded.
```

- [ ] **Step 3: Add the Ollama model-pull cell**

```python
import subprocess

MODEL = "qwen3:14b-fp16"

result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
if MODEL not in result.stdout:
    print(f"Pulling {MODEL} (this downloads ~30GB, may take a while)...")
    subprocess.run(["ollama", "pull", MODEL], check=True)
else:
    print(f"{MODEL} already pulled.")
```

Run this cell. Expected: either "already pulled" (if run before) or a progress bar completing
with no error. If it fails with an out-of-memory-style error or the download stalls, switch
`MODEL` to `"qwen3:14b-q8_0"` (~15GB, per the spec's documented fallback) and re-run.

- [ ] **Step 4: Add the sampling cell**

```python
SEED = 42
N_SAMPLE = 300

merged["text_to_classify"] = merged["content_text"].where(
    merged["content_text"].notna(), merged["content"]
)

# One row per physical paragraph/segment, not per (nsc_type, party) classification
# unit - otherwise a multi-party interjection (same text, several nsc_llm rows)
# would get classified and counted multiple times.
dedup = merged.drop_duplicates(subset=["paragraph_id", "segment_idx"], keep="first")
sample = dedup.sample(n=N_SAMPLE, random_state=SEED).reset_index(drop=True)

print(f"Deduplicated {len(merged):,} rows -> {len(dedup):,} unique paragraph/segment texts")
print(f"Sampled {len(sample):,} rows for LLM scoring")
sample[["paragraph_id", "state", "period", "affiliation", "text_to_classify"]].head()
```

Run this cell. Expected: prints showing `merged`'s row count deduplicating down to a smaller
number, then exactly 300 sampled rows; the preview table shows non-empty German text in
`text_to_classify` for a mix of affiliations.

- [ ] **Step 5: Add an Ollama smoke-test cell**

```python
import ollama

from impoliteness_lib import build_prompt, parse_response

_test_response = ollama.chat(
    model=MODEL,
    messages=build_prompt("Das ist doch eine Frechheit, Sie Lügner!"),
    think=False,
    format="json",
    options={"temperature": 0, "seed": SEED},
)
print(_test_response["message"]["content"])
print(parse_response(_test_response["message"]["content"]))
```

Run this cell. Expected: the raw output is a single-line JSON object (no chain-of-thought text
before it — if there is any, `think=False` isn't being honored; check the installed `ollama`
package version supports the `think` parameter), and `parse_response` returns
`{"impolite": True, "reason": ..., "raw_output": ...}` (this example sentence is clearly
impolite — an insult — so `impolite` must come back `True`, not `None`, or something is wrong
with the prompt/model before proceeding to the full run).

- [ ] **Step 6: Commit the notebook progress**

```bash
git add measurement/impoliteness_pilot.ipynb
git commit -m "Add Ollama setup and sampling cells to impoliteness pilot"
```

---

### Task 3: Run loop, output, and review section

**Files:**
- Modify: `measurement/impoliteness_pilot.ipynb` (append cells after Task 2's cells)

**Interfaces:**
- Consumes: `sample`, `MODEL`, `SEED` (Task 2), `build_prompt`/`parse_response` (Task 1).
- Produces: `predictions` (DataFrame), written to
  `DATA_ROOT/measurement/impoliteness_pilot_predictions.csv`.

- [ ] **Step 1: Add the run-loop cell**

```python
records = []
for i, row in sample.iterrows():
    response = ollama.chat(
        model=MODEL,
        messages=build_prompt(row["text_to_classify"]),
        think=False,
        format="json",
        options={"temperature": 0, "seed": SEED},
    )
    parsed = parse_response(response["message"]["content"])
    records.append({
        "paragraph_id": row["paragraph_id"],
        "state": row["state"],
        "period": row["period"],
        "date": row["date"],
        "affiliation": row["affiliation"],
        "content": row["text_to_classify"],
        "impolite": parsed["impolite"],
        "reason": parsed["reason"],
        "model_name": MODEL,
    })
    if (i + 1) % 25 == 0:
        print(f"  {i + 1}/{len(sample)} scored")

predictions = pd.DataFrame(records)
n_unparsed = predictions["impolite"].isna().sum()
print(f"Scored {len(predictions):,} paragraphs; {n_unparsed} unparseable responses")
```

Run this cell. Expected: progress printed every 25 rows up to 300, then a final line reporting
0 (or a small number of) unparseable responses. This will take a while (300 sequential local LLM
calls) — let it run to completion rather than interrupting.

- [ ] **Step 2: Add the save cell**

```python
out_path = Path(DATA_ROOT) / "measurement" / "impoliteness_pilot_predictions.csv"
out_path.parent.mkdir(parents=True, exist_ok=True)
predictions.to_csv(out_path, index=False)
print(f"Saved -> {out_path}")
```

Run this cell. Expected: the path prints and the file exists afterward (verify with `ls
"$DATA_ROOT/measurement/"` in a terminal, or a quick `Path(out_path).exists()` check).

- [ ] **Step 3: Add the overall/by-state rate cell**

```python
rate = predictions["impolite"].mean()
print(f"Predicted impoliteness rate: {rate:.1%} "
      f"({predictions['impolite'].sum():.0f} of {predictions['impolite'].notna().sum()} "
      f"parseable predictions)")
print()
print("By state:")
print(predictions.groupby("state")["impolite"].mean().sort_values(ascending=False)
      .apply(lambda x: f"{x:.1%}").to_string())
```

Run this cell. Expected: an overall percentage plus a per-state breakdown table with no errors.
There's no "correct" number to check against yet (that's the whole point of the pilot) — just
confirm it runs and produces plausible-looking percentages (not 0% or 100% across the board,
which would suggest the model is defaulting to one answer regardless of input).

- [ ] **Step 4: Add the manual-review examples cell**

```python
print("-- Examples predicted impolite --")
for _, row in predictions[predictions["impolite"] == True].head(10).iterrows():
    print(f"[{row['state']} {row['period']}] {row['content']}")
    print(f"  -> reason: {row['reason']}")
    print()
```

Run this cell and actually read the output: for each example, does the text look genuinely
impolite, and does the model's stated `reason` make sense? This is the main quality signal this
pilot produces — flag it if several examples look like clear false positives (e.g. ordinary
procedural speech flagged as impolite).

- [ ] **Step 5: Add the gold-label cross-check cell**

```python
gold = pd.read_csv("../labelling/annotations_output.csv", dtype={"para_id": str})
gold_neutral = gold[gold["politeness"] == "neutral"]

check = predictions.merge(
    gold_neutral[["para_id", "politeness"]],
    left_on="paragraph_id", right_on="para_id", how="inner",
)
print(f"Overlap with gold neutral rows: {len(check)}")
if len(check):
    print(check[["paragraph_id", "impolite", "content"]].to_string(index=False))
    n_flagged = (check["impolite"] == True).sum()
    print(f"\n{n_flagged} of {len(check)} gold-neutral rows flagged impolite by the model "
          f"(should be 0 or very low; if not, revisit the prompt)")
else:
    print("No overlap between this sample and the 36 gold-labeled rows - expected, since "
          "they're separate random draws from a much larger pool. This check only becomes "
          "meaningful once the gold set is larger or the sample size increases.")
```

Run this cell. Expected: most likely "no overlap" (36 gold rows vs. a 300-row sample out of
millions of candidates) — that's a normal outcome, not a bug. This cell exists so the check runs
automatically and becomes useful once either the gold set or the sample size grows.

- [ ] **Step 6: Commit**

```bash
git add measurement/impoliteness_pilot.ipynb
git commit -m "Add run loop, output, and review section to impoliteness pilot"
```
