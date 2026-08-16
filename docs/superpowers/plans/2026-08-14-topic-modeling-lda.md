# Topic Modeling (LDA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable pre/post-AfD-entry speech dataset and an exploratory LDA topic-modeling
pipeline (sklearn + gensim, compared) over German state-parliament speeches, with caching so
repeated runs with different parameters don't re-do expensive work.

**Architecture:** A one-time ETL script (`preprocessing/afd_period_window.py`) builds a shared,
reusable Parquet file of speech-level documents scoped to each state's pre/post-AfD-entry
legislative period. A library module (`measurement/topic_modeling_lib.py`) provides small, unit
tested functions for loading/filtering that dataset, preprocessing text, vectorizing, fitting both
sklearn and gensim LDA across a range of topic counts, and caching every expensive intermediate to
disk. A thin notebook (`measurement/topic_modeling.ipynb`) wires these functions together for
actual exploration.

**Tech Stack:** Python. `preprocessing/afd_period_window.py` runs on the project's existing
`norm_env` (pandas only, no new deps). `measurement/topic_modeling_lib.py` and
`measurement/topic_modeling.ipynb` run on a new, dedicated `topic_modeling_env` (Python 3.11) —
see the note on why below. Both use `pandas`, `pyarrow`; the topic-modeling side additionally
uses `spacy` (`de_core_news_lg`), `gensim`, `scikit-learn`, `joblib`, `jupyter`. Tests via
`pytest`.

**Why a second virtualenv:** the project's `norm_env` is pinned to Python 3.14 (`.python-version`).
`gensim` 4.4.0 fails to build from source on 3.14, and the only prebuilt wheel PyPI has for 3.14 is
an ancient, scipy-incompatible `gensim` 0.10.1 (2014) — confirmed by trying both during planning.
`gensim` 4.4.0 installs and imports cleanly on Python 3.11. Rather than downgrading the whole
project's `norm_env` (affecting every other pipeline) for one new module, Task 1 creates a second,
narrowly-scoped venv. `preprocessing/afd_period_window.py` needs no new packages, so it keeps
using `norm_env` — only the topic-modeling code needs the new environment.

## Global Constraints

- Document unit = one speech (`speech_id`). Text = `paragraphs.content` grouped by `speech_id`,
  ordered by `protocol_position`/`segment_position`, excluding `affiliation == "nsc"` rows.
- Scope = pre/post AfD-entry window using the `period` variable, per state: pre-window = the
  period immediately before the state's AfD-entry period; post-window = the period
  containing/starting at the entry date.
- This dataset is built **once, for all 16 states**, in `preprocessing/` (ETL, not construct
  measurement) and written to `DATA_ROOT/processed/speeches_afd_prepost.parquet`. Downstream code
  reads this file — it never rebuilds the window itself.
- Preprocessing uses spaCy `de_core_news_lg` (not `sm`) and must be a swappable function, not
  hardcoded, so it can be replaced later without touching the rest of the pipeline.
- Modeling runs **both** sklearn `LatentDirichletAllocation` (log-likelihood random search over
  K) and gensim `LdaModel` (`c_v` coherence scan over the same K range) and compares them — this
  is not optional, both methods are part of the design.
- Every expensive step (preprocessing, vectorization, each model fit) is timed; elapsed time is
  logged and stored alongside cached results.
- Expensive intermediates are cached to disk, keyed by dataset params + preprocessing version + K,
  under `measurement/run_history/topic_modeling/`.
- Plain (unseeded) LDA only — no keyword-assisted/seeded topics, no `preText` integration, no
  full-corpus production run. See spec `docs/superpowers/specs/2026-08-14-topic-modeling-lda-
  design.md` (local-only, gitignored) for full rationale.

---

### Task 1: Environment setup — dedicated `topic_modeling_env` (Python 3.11)

**Files:**
- Create: `topic_modeling_env` (a new Python 3.11 virtualenv at the repo root — not
  `norm_env`; see the Tech Stack note above for why)
- Modify: `.gitignore` (add the new venv directory, matching the existing `norm_env/` entry)

**Interfaces:**
- Produces: a `topic_modeling_env` with `gensim`, `scikit-learn`, `spacy` +
  `de_core_news_lg`, and `jupyter` installed, available to every later task in this plan that
  touches `measurement/topic_modeling_lib.py` or `measurement/topic_modeling.ipynb` (Tasks
  5-11). Tasks 2-4 (`preprocessing/afd_period_window.py`) do not use this venv — they use the
  existing `norm_env`, since they need no new packages.

- [ ] **Step 1: Confirm Python 3.11 is available**

Run: `/opt/homebrew/bin/python3.11 --version`
Expected: `Python 3.11.x`. (Confirmed present on this machine during planning; if this specific
path doesn't exist in your environment, use whatever `python3.11` resolves to via `which
python3.11`.)

- [ ] **Step 2: Create the venv**

Run:
```bash
/opt/homebrew/bin/python3.11 -m venv topic_modeling_env
```

- [ ] **Step 3: Install the new Python packages**

Run:
```bash
topic_modeling_env/bin/pip install gensim scikit-learn spacy jupyter python-dotenv
```
Expected: all five install successfully with prebuilt wheels (no source-build errors — this is
the known-good combination confirmed during planning, unlike Python 3.14). `python-dotenv` is
needed by Task 11's notebook to load `DATA_ROOT` from `.env` — omitted from an earlier draft of
this step and caught during Task 11's execution; included here so a fresh rebuild of this venv
doesn't hit the same `ModuleNotFoundError`.

- [ ] **Step 4: Download the German spaCy model**

Run:
```bash
topic_modeling_env/bin/python -m spacy download de_core_news_lg
```
If this fails with an environment-detection error (observed once during planning on a
differently-configured venv, cause not fully diagnosed), fall back to installing the model
wheel directly:
```bash
topic_modeling_env/bin/pip install https://github.com/explosion/spacy-models/releases/download/de_core_news_lg-3.8.0/de_core_news_lg-3.8.0-py3-none-any.whl
```

- [ ] **Step 5: Verify the install**

Run:
```bash
topic_modeling_env/bin/python -c "import gensim, sklearn, spacy; nlp = spacy.load('de_core_news_lg'); print(gensim.__version__, sklearn.__version__, nlp.meta['name'])"
```
Expected: prints three version/name values with no import errors (in particular, no
`ImportError: cannot import name 'triu' from 'scipy.linalg.basic'` — the failure signature of
the wrong gensim version).

- [ ] **Step 6: Register a Jupyter kernel for this venv**

Task 11's notebook must run on `topic_modeling_env`, not whatever kernel happens to be
registered globally. Register one explicitly:
```bash
topic_modeling_env/bin/python -m ipykernel install --user --name topic_modeling_env --display-name "topic_modeling_env (py3.11)"
```
Task 11 references this kernel name (`topic_modeling_env`) both in the notebook's own metadata
and in the `nbconvert` command that executes it.

- [ ] **Step 7: Gitignore the new venv**

Add to `.gitignore`, in the existing `# Python` section next to `norm_env/`:
```
topic_modeling_env/
```

- [ ] **Step 8: Commit**

```bash
git add .gitignore
git commit -m "Add topic_modeling_env (Python 3.11) for gensim/sklearn/spacy work"
```

---

### Task 2: `preprocessing/afd_period_window.py` — `derive_period_windows`

**Files:**
- Create: `preprocessing/afd_period_window.py`
- Test: `preprocessing/test_afd_period_window.py`

**Interfaces:**
- Produces: `derive_period_windows(protocols: pd.DataFrame, afd_entry: pd.DataFrame) -> dict[str,
  dict[str, int]]` — e.g. `{"by": {"pre": 17, "post": 18}}`. `protocols` has columns `state`
  (str), `period` (int), `date` (datetime64 or ISO string, one row per protocol/sitting).
  `afd_entry` has columns `state` (str), `entry_date` (datetime64), matching
  `DATA_ROOT/processed/afd_entry_dates.csv`'s shape (already used by
  `measurement/impoliteness_lib.py`).

- [ ] **Step 1: Write the failing test**

Create `preprocessing/test_afd_period_window.py`:

```python
import pandas as pd

from afd_period_window import derive_period_windows


def test_derive_period_windows_picks_period_starting_at_or_after_entry():
    protocols = pd.DataFrame({
        "state": ["by", "by", "by", "th", "th"],
        "period": [16, 17, 18, 5, 6],
        "date": pd.to_datetime([
            "2008-10-20", "2013-10-07", "2018-11-05", "2014-01-01", "2014-10-14",
        ]),
    })
    afd_entry = pd.DataFrame({
        "state": ["by", "th"],
        "entry_date": pd.to_datetime(["2018-11-05", "2014-10-14"]),
    })

    windows = derive_period_windows(protocols, afd_entry)

    assert windows == {
        "by": {"pre": 17, "post": 18},
        "th": {"pre": 5, "post": 6},
    }


def test_derive_period_windows_skips_state_with_no_prior_period():
    protocols = pd.DataFrame({
        "state": ["sn"],
        "period": [1],
        "date": pd.to_datetime(["2014-09-01"]),
    })
    afd_entry = pd.DataFrame({
        "state": ["sn"],
        "entry_date": pd.to_datetime(["2014-09-29"]),
    })

    windows = derive_period_windows(protocols, afd_entry)

    assert windows == {}


def test_derive_period_windows_skips_state_not_in_afd_entry_table():
    protocols = pd.DataFrame({
        "state": ["hh", "hh"],
        "period": [1, 2],
        "date": pd.to_datetime(["2010-01-01", "2015-09-16"]),
    })
    afd_entry = pd.DataFrame({"state": [], "entry_date": pd.to_datetime([])})

    windows = derive_period_windows(protocols, afd_entry)

    assert windows == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd preprocessing && ../norm_env/bin/python -m pytest test_afd_period_window.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'afd_period_window'`

- [ ] **Step 3: Write minimal implementation**

Create `preprocessing/afd_period_window.py`:

```python
"""Builds the shared pre/post-AfD-entry speech dataset used by any pipeline that needs
speeches scoped to a state's legislative period immediately before vs. immediately after
AfD entry (currently: measurement/topic_modeling_lib.py). See
docs/superpowers/specs/2026-08-14-topic-modeling-lda-design.md (local-only) for rationale.
"""
import os

import pandas as pd

NON_SPEECH_AFFILIATION = "nsc"


def derive_period_windows(protocols: pd.DataFrame, afd_entry: pd.DataFrame) -> dict[str, dict[str, int]]:
    """For each state in `afd_entry`, find the legislative period that starts at/after the
    state's AfD entry date (`post`) and the period immediately before it (`pre`).

    States with no prior period available (the first known period is already `post`) or not
    present in `afd_entry` are omitted from the result.
    """
    period_starts = (
        protocols.groupby(["state", "period"])["date"].min().reset_index()
    )
    entry_by_state = afd_entry.set_index("state")["entry_date"]

    windows: dict[str, dict[str, int]] = {}
    for state, group in period_starts.groupby("state"):
        if state not in entry_by_state.index:
            continue
        entry_date = entry_by_state[state]
        group = group.sort_values("period").reset_index(drop=True)

        post_candidates = group[group["date"] >= entry_date]
        if post_candidates.empty:
            continue
        post_period = int(post_candidates.iloc[0]["period"])
        post_idx = group.index[group["period"] == post_period][0]
        if post_idx == 0:
            continue

        pre_period = int(group.iloc[post_idx - 1]["period"])
        windows[state] = {"pre": pre_period, "post": post_period}

    return windows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd preprocessing && ../norm_env/bin/python -m pytest test_afd_period_window.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add preprocessing/afd_period_window.py preprocessing/test_afd_period_window.py
git commit -m "Add derive_period_windows for pre/post-AfD-entry period lookup"
```

---

### Task 3: `preprocessing/afd_period_window.py` — `build_speech_documents`

**Files:**
- Modify: `preprocessing/afd_period_window.py`
- Test: `preprocessing/test_afd_period_window.py`

**Interfaces:**
- Consumes: nothing from Task 2 directly (takes a `period_windows` dict of the same shape
  `derive_period_windows` produces, but as a parameter — not coupled by import).
- Produces: `build_speech_documents(paragraphs: pd.DataFrame, period_windows: dict[str,
  dict[str, int]]) -> pd.DataFrame` with columns `speech_id, state, period, pre_post, date,
  text`. `paragraphs` has columns `speech_id, state, period, protocol_position,
  segment_position, content, affiliation, date` (matching
  `stateparl_v3_paragraphs.parquet`'s real schema, minus the columns this function doesn't
  use).

- [ ] **Step 1: Write the failing test**

Append to `preprocessing/test_afd_period_window.py`:

```python
from afd_period_window import build_speech_documents


def test_build_speech_documents_concatenates_ordered_and_excludes_nsc():
    paragraphs = pd.DataFrame({
        "speech_id": ["s1", "s1", "s1", "s2"],
        "state": ["by", "by", "by", "by"],
        "period": [18, 18, 18, 17],
        "protocol_position": [1, 2, 3, 1],
        "segment_position": [0, 0, 0, 0],
        "content": ["Erstens.", "[Zwischenruf]", "Zweitens.", "Ganzer Satz."],
        "affiliation": ["spd", "nsc", "spd", "cdu"],
        "date": pd.to_datetime(["2019-01-01", "2019-01-01", "2019-01-01", "2014-01-01"]),
    })
    period_windows = {"by": {"pre": 17, "post": 18}}

    docs = build_speech_documents(paragraphs, period_windows)

    docs = docs.set_index("speech_id")
    assert docs.loc["s1", "text"] == "Erstens. Zweitens."
    assert docs.loc["s1", "pre_post"] == "post"
    assert docs.loc["s2", "text"] == "Ganzer Satz."
    assert docs.loc["s2", "pre_post"] == "pre"


def test_build_speech_documents_drops_paragraphs_outside_any_window():
    paragraphs = pd.DataFrame({
        "speech_id": ["s1", "s2"],
        "state": ["by", "by"],
        "period": [18, 16],
        "protocol_position": [1, 1],
        "segment_position": [0, 0],
        "content": ["In window.", "Outside window."],
        "affiliation": ["spd", "spd"],
        "date": pd.to_datetime(["2019-01-01", "2010-01-01"]),
    })
    period_windows = {"by": {"pre": 17, "post": 18}}

    docs = build_speech_documents(paragraphs, period_windows)

    assert list(docs["speech_id"]) == ["s1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd preprocessing && ../norm_env/bin/python -m pytest test_afd_period_window.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_speech_documents'`

- [ ] **Step 3: Write minimal implementation**

Add to `preprocessing/afd_period_window.py` (after `derive_period_windows`):

```python
def build_speech_documents(paragraphs: pd.DataFrame, period_windows: dict[str, dict[str, int]]) -> pd.DataFrame:
    """One row per speech falling inside its state's pre- or post-AfD-entry period, with
    paragraph content concatenated in reading order. Excludes `nsc` (interjection) rows --
    those interrupt a speech, they aren't part of it."""
    keep_mask = pd.Series(False, index=paragraphs.index)
    pre_post_lookup: dict[tuple[str, int], str] = {}
    for state, window in period_windows.items():
        for label, period in window.items():
            in_window = (paragraphs["state"] == state) & (paragraphs["period"] == period)
            keep_mask |= in_window
            pre_post_lookup[(state, period)] = label

    scoped = paragraphs[keep_mask & (paragraphs["affiliation"] != NON_SPEECH_AFFILIATION)].copy()
    scoped = scoped.sort_values(["speech_id", "protocol_position", "segment_position"])

    grouped = scoped.groupby("speech_id").agg(
        state=("state", "first"),
        period=("period", "first"),
        date=("date", "first"),
        text=("content", lambda s: " ".join(s.dropna())),
    ).reset_index()

    grouped["pre_post"] = [
        pre_post_lookup[(row.state, row.period)] for row in grouped.itertuples()
    ]

    return grouped[["speech_id", "state", "period", "pre_post", "date", "text"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd preprocessing && ../norm_env/bin/python -m pytest test_afd_period_window.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add preprocessing/afd_period_window.py preprocessing/test_afd_period_window.py
git commit -m "Add build_speech_documents for pre/post-AfD speech-level text"
```

---

### Task 4: `preprocessing/afd_period_window.py` — script entry point, run against real data

**Files:**
- Modify: `preprocessing/afd_period_window.py`

**Interfaces:**
- Consumes: `derive_period_windows` (Task 2), `build_speech_documents` (Task 3).
- Produces: `DATA_ROOT/processed/speeches_afd_prepost.parquet` (on disk — not a Python
  interface, but the file every later task in `measurement/topic_modeling_lib.py` reads).

- [ ] **Step 1: Add the `main()` function**

Add to `preprocessing/afd_period_window.py`:

```python
def main(data_root: str) -> None:
    raw = os.path.join(data_root, "raw")
    proc = os.path.join(data_root, "processed")
    v3 = os.path.join(raw, "stateparl_v3_parquet")

    protocols = pd.read_parquet(os.path.join(v3, "stateparl_v3_protocols.parquet"))
    protocols["date"] = pd.to_datetime(protocols["date"])

    afd_entry = pd.read_csv(os.path.join(proc, "afd_entry_dates.csv"), parse_dates=["entry_date"])

    paragraphs = pd.read_parquet(os.path.join(v3, "stateparl_v3_paragraphs.parquet"))
    paragraphs["date"] = pd.to_datetime(paragraphs["date"])

    windows = derive_period_windows(protocols, afd_entry)
    print(f"Derived pre/post periods for {len(windows)} of {afd_entry['state'].nunique()} states")

    docs = build_speech_documents(paragraphs, windows)
    print(f"Built {len(docs):,} speech documents across {docs['state'].nunique()} states")

    out_path = os.path.join(proc, "speeches_afd_prepost.parquet")
    docs.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main(os.environ["DATA_ROOT"])
```

- [ ] **Step 2: Run it against the real corpus**

Run: `norm_env/bin/python preprocessing/afd_period_window.py`
Expected: prints a window count (up to 16 states), a document count, and the output path; exits
0 with no traceback.

- [ ] **Step 3: Sanity-check the output**

Run:
```bash
norm_env/bin/python -c "
import pandas as pd, os
df = pd.read_parquet(os.path.join(os.environ['DATA_ROOT'], 'processed', 'speeches_afd_prepost.parquet'))
print(df.shape)
print(df['pre_post'].value_counts())
print(df['state'].nunique(), 'states')
print(df['text'].str.len().describe())
"
```
Expected: a few hundred thousand rows, both `pre` and `post` represented, close to 16 states,
`text` lengths mostly non-trivial (not empty/near-zero on average).

- [ ] **Step 4: Commit**

```bash
git add preprocessing/afd_period_window.py
git commit -m "Add afd_period_window.py script entry point"
```

(The output Parquet file lives under `DATA_ROOT`, outside the repo, per this repo's existing
data-storage convention — nothing to add there.)

---

### Task 5: `measurement/topic_modeling_lib.py` — timing helper

**Files:**
- Create: `measurement/topic_modeling_lib.py`
- Test: `measurement/test_topic_modeling_lib.py`

**Interfaces:**
- Produces: `timed(label: str, log: list[dict] | None = None)` — a context manager. On exit,
  prints `f"[{label}] {elapsed:.2f}s"` and, if `log` is given, appends `{"step": label,
  "seconds": elapsed}` to it. Every later task that fits a model wraps the fit in `timed(...)`.

- [ ] **Step 1: Write the failing test**

Create `measurement/test_topic_modeling_lib.py`:

```python
import time

from topic_modeling_lib import timed


def test_timed_appends_to_log():
    log = []

    with timed("sleep-step", log=log):
        time.sleep(0.01)

    assert len(log) == 1
    assert log[0]["step"] == "sleep-step"
    assert log[0]["seconds"] >= 0.01


def test_timed_without_log_does_not_raise():
    with timed("no-log-step"):
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'topic_modeling_lib'`

- [ ] **Step 3: Write minimal implementation**

Create `measurement/topic_modeling_lib.py`:

```python
"""Reusable functions for the exploratory LDA topic-modeling pipeline over
speeches_afd_prepost.parquet (built by preprocessing/afd_period_window.py). See
docs/superpowers/specs/2026-08-14-topic-modeling-lda-design.md (local-only) for the full design
rationale.
"""
import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def timed(label: str, log: list[dict] | None = None):
    """Times the wrapped block, printing elapsed seconds and optionally appending
    {"step": label, "seconds": elapsed} to `log` -- used to estimate full-corpus runtime from a
    small sample/single-state run before committing to a bigger one."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"[{label}] {elapsed:.2f}s")
    if log is not None:
        log.append({"step": label, "seconds": elapsed})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add measurement/topic_modeling_lib.py measurement/test_topic_modeling_lib.py
git commit -m "Add timed() context manager for topic modeling pipeline"
```

---

### Task 6: `measurement/topic_modeling_lib.py` — caching (`cache_key`, `save_cache`, `load_cache`)

**Files:**
- Modify: `measurement/topic_modeling_lib.py`
- Test: `measurement/test_topic_modeling_lib.py`

**Interfaces:**
- Produces:
  - `cache_key(params: dict) -> str` — deterministic, order-independent 12-char hex digest.
  - `cache_path(params: dict, suffix: str) -> Path` — under `measurement/run_history/
    topic_modeling/`.
  - `save_cache(obj, params: dict, suffix: str) -> Path`
  - `load_cache(params: dict, suffix: str)` — returns `None` if no cache exists for those
    params, otherwise the unpickled object.
- Every later task that produces an expensive result (`gensim_coherence_scan`,
  `sklearn_loglikelihood_search`) takes a `params: dict` argument and calls these to cache its
  output.

- [ ] **Step 1: Write the failing test**

Append to `measurement/test_topic_modeling_lib.py`:

```python
from topic_modeling_lib import cache_key, load_cache, save_cache


def test_cache_key_is_order_independent():
    a = cache_key({"state": "by", "k": 10})
    b = cache_key({"k": 10, "state": "by"})

    assert a == b


def test_cache_key_differs_for_different_params():
    a = cache_key({"state": "by", "k": 10})
    b = cache_key({"state": "by", "k": 20})

    assert a != b


def test_save_and_load_cache_roundtrip(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    params = {"state": "th", "sample_n": 500}
    save_cache({"hello": "world"}, params, suffix=".pkl")

    assert load_cache(params, suffix=".pkl") == {"hello": "world"}


def test_load_cache_returns_none_when_missing(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    assert load_cache({"nope": True}, suffix=".pkl") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: FAIL — `ImportError: cannot import name 'cache_key'`

- [ ] **Step 3: Write minimal implementation**

Add to `measurement/topic_modeling_lib.py`:

```python
import joblib

CACHE_DIR = Path(__file__).resolve().parent / "run_history" / "topic_modeling"


def cache_key(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha1(canonical.encode()).hexdigest()[:12]


def cache_path(params: dict, suffix: str) -> Path:
    return CACHE_DIR / f"{cache_key(params)}{suffix}"


def save_cache(obj, params: dict, suffix: str) -> Path:
    path = cache_path(params, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)
    return path


# joblib.load uses pickle under the hood, but this cache only ever reads files this same
# pipeline wrote to a local directory under the repo -- never remote or user-supplied data --
# so there's no untrusted-deserialization risk here.
def load_cache(params: dict, suffix: str):
    path = cache_path(params, suffix)
    return joblib.load(path) if path.exists() else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add measurement/topic_modeling_lib.py measurement/test_topic_modeling_lib.py
git commit -m "Add disk caching for topic modeling pipeline results"
```

---

### Task 7: `measurement/topic_modeling_lib.py` — `load_corpus`

**Files:**
- Modify: `measurement/topic_modeling_lib.py`
- Test: `measurement/test_topic_modeling_lib.py`

**Interfaces:**
- Produces: `load_corpus(data_root: str, states: list[str] | None = None, pre_post: str | None
  = None, sample_n: int | None = None, seed: int = 42) -> pd.DataFrame` — reads
  `speeches_afd_prepost.parquet`, filters by `states` (list, or `None` = all) and `pre_post`
  (`"pre"`, `"post"`, or `None` = both), then optionally draws a fixed-seed random sample of
  size `sample_n`. Returns the same columns as `build_speech_documents`'s output.

- [ ] **Step 1: Write the failing test**

Append to `measurement/test_topic_modeling_lib.py`:

```python
import pandas as pd

from topic_modeling_lib import load_corpus


def _write_fixture_corpus(data_root):
    proc = data_root / "processed"
    proc.mkdir(parents=True)
    df = pd.DataFrame({
        "speech_id": ["s1", "s2", "s3", "s4"],
        "state": ["by", "by", "th", "th"],
        "period": [18, 17, 6, 5],
        "pre_post": ["post", "pre", "post", "pre"],
        "date": pd.to_datetime(["2019-01-01", "2014-01-01", "2015-01-01", "2013-01-01"]),
        "text": ["a", "b", "c", "d"],
    })
    df.to_parquet(proc / "speeches_afd_prepost.parquet", index=False)


def test_load_corpus_filters_by_state_and_pre_post(tmp_path):
    _write_fixture_corpus(tmp_path)

    result = load_corpus(str(tmp_path), states=["by"], pre_post="post")

    assert list(result["speech_id"]) == ["s1"]


def test_load_corpus_defaults_to_everything(tmp_path):
    _write_fixture_corpus(tmp_path)

    result = load_corpus(str(tmp_path))

    assert len(result) == 4


def test_load_corpus_samples_deterministically(tmp_path):
    _write_fixture_corpus(tmp_path)

    first = load_corpus(str(tmp_path), sample_n=2, seed=7)
    second = load_corpus(str(tmp_path), sample_n=2, seed=7)

    assert list(first["speech_id"]) == list(second["speech_id"])
    assert len(first) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_corpus'`

- [ ] **Step 3: Write minimal implementation**

Add to `measurement/topic_modeling_lib.py`:

```python
import os

import pandas as pd


def load_corpus(
    data_root: str,
    states: list[str] | None = None,
    pre_post: str | None = None,
    sample_n: int | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Reads DATA_ROOT/processed/speeches_afd_prepost.parquet (built once by
    preprocessing/afd_period_window.py) and filters/samples it -- this function never rebuilds
    the pre/post-AfD window itself."""
    path = os.path.join(data_root, "processed", "speeches_afd_prepost.parquet")
    df = pd.read_parquet(path)

    if states is not None:
        df = df[df["state"].isin(states)]
    if pre_post is not None:
        df = df[df["pre_post"] == pre_post]
    if sample_n is not None:
        df = df.sample(n=sample_n, random_state=seed)

    return df.reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add measurement/topic_modeling_lib.py measurement/test_topic_modeling_lib.py
git commit -m "Add load_corpus for filtering/sampling the shared AfD-window speech dataset"
```

---

### Task 8: `measurement/topic_modeling_lib.py` — swappable preprocessing

**Files:**
- Modify: `measurement/topic_modeling_lib.py`
- Test: `measurement/test_topic_modeling_lib.py`

**Interfaces:**
- Produces: `make_spacy_preprocessor(nlp) -> Callable[[list[str]], list[list[str]]]`. Takes an
  already-loaded spaCy `Language` object (so the caller controls which model — `de_core_news_lg`
  in the real notebook, a lightweight `spacy.blank("de")` in tests) and returns a function that
  tokenizes/lemmatizes/lowercases a list of raw document strings, dropping stopwords and
  non-alphabetic tokens of length <= 2. This returned function — not the loading of `nlp` — is
  the "swappable preprocessing" piece later tasks depend on: `build_gensim_corpus` and
  `build_sklearn_corpus` (Tasks 9-10) both take `tokenized_docs: list[list[str]]`, produced by
  calling this function's return value — they never call spaCy directly.

- [ ] **Step 1: Write the failing test**

Append to `measurement/test_topic_modeling_lib.py`:

```python
import spacy

from topic_modeling_lib import make_spacy_preprocessor


def test_make_spacy_preprocessor_lowercases_and_drops_short_and_nonalpha_tokens():
    nlp = spacy.blank("de")
    preprocess = make_spacy_preprocessor(nlp)

    result = preprocess(["Die Politik ist 2019 wichtig."])

    assert result == [["politik", "wichtig"]]


def test_make_spacy_preprocessor_drops_stopwords():
    nlp = spacy.blank("de")
    preprocess = make_spacy_preprocessor(nlp)

    result = preprocess(["Und dann kam die Regierung."])

    assert "und" not in result[0]
    assert "dann" not in result[0]
    assert "regierung" in result[0]


def test_make_spacy_preprocessor_handles_multiple_documents():
    nlp = spacy.blank("de")
    preprocess = make_spacy_preprocessor(nlp)

    result = preprocess(["Erste Rede.", "Zweite Rede."])

    assert len(result) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: FAIL — `ImportError: cannot import name 'make_spacy_preprocessor'`

- [ ] **Step 3: Write minimal implementation**

Add to `measurement/topic_modeling_lib.py`:

```python
from typing import Callable


def make_spacy_preprocessor(nlp) -> Callable[[list[str]], list[list[str]]]:
    """Returns a tokenize/lemmatize/stopword-removal function bound to `nlp`. Passed a
    spacy.blank("de") in tests (fast, no model download) and spacy.load("de_core_news_lg") in
    the real notebook -- this indirection is what makes preprocessing swappable without
    changing build_gensim_corpus/build_sklearn_corpus, which only ever see the token lists this
    produces."""

    def _preprocess(texts: list[str]) -> list[list[str]]:
        docs = nlp.pipe(texts, disable=[p for p in ("parser", "ner") if p in nlp.pipe_names])
        result = []
        for doc in docs:
            tokens = [
                tok.lemma_.lower()
                for tok in doc
                if tok.is_alpha and not tok.is_stop and len(tok.lemma_) > 2
            ]
            result.append(tokens)
        return result

    return _preprocess
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add measurement/topic_modeling_lib.py measurement/test_topic_modeling_lib.py
git commit -m "Add swappable spaCy preprocessing function"
```

---

### Task 9: `measurement/topic_modeling_lib.py` — gensim vectorization + coherence scan

**Files:**
- Modify: `measurement/topic_modeling_lib.py`
- Test: `measurement/test_topic_modeling_lib.py`

**Interfaces:**
- Consumes: `tokenized_docs: list[list[str]]` (shape produced by Task 8's preprocessor),
  `timed` (Task 5), `save_cache`/`load_cache` (Task 6).
- Produces:
  - `build_gensim_corpus(tokenized_docs: list[list[str]]) -> tuple[gensim.corpora.Dictionary,
    list]`
  - `gensim_coherence_scan(tokenized_docs: list[list[str]], dictionary, corpus, k_range:
    list[int], params: dict, seed: int = 42) -> pd.DataFrame` with columns `k, coherence,
    seconds, model` — one row per `k` in `k_range`. Caches the returned DataFrame under
    `params | {"method": "gensim"}` and returns the cached copy on a repeat call with the same
    `params`.

- [ ] **Step 1: Write the failing test**

Append to `measurement/test_topic_modeling_lib.py`:

```python
from topic_modeling_lib import build_gensim_corpus, gensim_coherence_scan

_TOY_DOCS = [
    ["politik", "steuer", "haushalt"],
    ["steuer", "haushalt", "budget"],
    ["schule", "bildung", "lehrer"],
    ["bildung", "lehrer", "unterricht"],
    ["politik", "haushalt", "budget"],
    ["schule", "unterricht", "lehrer"],
]


def test_build_gensim_corpus_shapes():
    dictionary, corpus = build_gensim_corpus(_TOY_DOCS)

    assert len(corpus) == len(_TOY_DOCS)
    assert dictionary.token2id  # non-empty vocabulary


def test_gensim_coherence_scan_returns_one_row_per_k(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    dictionary, corpus = build_gensim_corpus(_TOY_DOCS)
    result = gensim_coherence_scan(
        _TOY_DOCS, dictionary, corpus, k_range=[2, 3], params={"test": "gensim-scan"},
    )

    assert list(result["k"]) == [2, 3]
    assert result["coherence"].notna().all()
    assert (result["seconds"] >= 0).all()


def test_gensim_coherence_scan_uses_cache_on_repeat_call(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    dictionary, corpus = build_gensim_corpus(_TOY_DOCS)
    params = {"test": "gensim-scan-cache"}
    first = gensim_coherence_scan(_TOY_DOCS, dictionary, corpus, k_range=[2], params=params)
    second = gensim_coherence_scan(_TOY_DOCS, dictionary, corpus, k_range=[2], params=params)

    assert list(first["k"]) == list(second["k"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_gensim_corpus'`

- [ ] **Step 3: Write minimal implementation**

Add to `measurement/topic_modeling_lib.py`:

```python
from gensim import corpora
from gensim.models import CoherenceModel, LdaModel


def build_gensim_corpus(tokenized_docs: list[list[str]]) -> tuple[corpora.Dictionary, list]:
    dictionary = corpora.Dictionary(tokenized_docs)
    corpus = [dictionary.doc2bow(doc) for doc in tokenized_docs]
    return dictionary, corpus


def gensim_coherence_scan(
    tokenized_docs: list[list[str]],
    dictionary,
    corpus: list,
    k_range: list[int],
    params: dict,
    seed: int = 42,
) -> pd.DataFrame:
    """Fits a gensim LdaModel per k in k_range, scored by c_v coherence. Cached under
    params | {"method": "gensim"} so re-running the notebook with unchanged params/k_range
    loads from disk instead of re-fitting."""
    cache_params = {**params, "method": "gensim", "k_range": list(k_range)}
    cached = load_cache(cache_params, suffix=".pkl")
    if cached is not None:
        return cached

    rows = []
    for k in k_range:
        start = time.perf_counter()
        model = LdaModel(corpus=corpus, id2word=dictionary, num_topics=k, random_state=seed)
        coherence = CoherenceModel(
            model=model, texts=tokenized_docs, dictionary=dictionary, coherence="c_v",
        ).get_coherence()
        elapsed = time.perf_counter() - start
        print(f"[gensim k={k}] {elapsed:.2f}s, coherence={coherence:.4f}")
        rows.append({"k": k, "coherence": coherence, "seconds": elapsed, "model": model})

    result = pd.DataFrame(rows)
    save_cache(result, cache_params, suffix=".pkl")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add measurement/topic_modeling_lib.py measurement/test_topic_modeling_lib.py
git commit -m "Add gensim coherence scan with caching"
```

---

### Task 10: `measurement/topic_modeling_lib.py` — sklearn vectorization + log-likelihood search

**Files:**
- Modify: `measurement/topic_modeling_lib.py`
- Test: `measurement/test_topic_modeling_lib.py`

**Interfaces:**
- Consumes: `tokenized_docs: list[list[str]]` (same shape as Task 9), `save_cache`/`load_cache`
  (Task 6).
- Produces:
  - `build_sklearn_corpus(tokenized_docs: list[list[str]]) -> tuple[CountVectorizer,
    scipy.sparse.spmatrix]`
  - `sklearn_loglikelihood_search(dtm, k_range: list[int], params: dict, n_iter: int | None =
    None, seed: int = 42) -> pd.DataFrame` with columns `k, log_likelihood, seconds, model` —
    fits on an 80% train split, scores on the held-out 20%, for `n_iter` randomly chosen values
    of `k` from `k_range` (defaults to all of `k_range` if `n_iter` is `None` or >=
    `len(k_range)`). Cached the same way as Task 9's scan.

- [ ] **Step 1: Write the failing test**

Append to `measurement/test_topic_modeling_lib.py`:

```python
from topic_modeling_lib import build_sklearn_corpus, sklearn_loglikelihood_search


def test_build_sklearn_corpus_shapes():
    vectorizer, dtm = build_sklearn_corpus(_TOY_DOCS)

    assert dtm.shape[0] == len(_TOY_DOCS)
    assert len(vectorizer.vocabulary_) > 0


def test_sklearn_loglikelihood_search_returns_one_row_per_k(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    _, dtm = build_sklearn_corpus(_TOY_DOCS)
    result = sklearn_loglikelihood_search(
        dtm, k_range=[2, 3], params={"test": "sklearn-search"},
    )

    assert sorted(result["k"]) == [2, 3]
    assert (result["seconds"] >= 0).all()


def test_sklearn_loglikelihood_search_respects_n_iter(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    _, dtm = build_sklearn_corpus(_TOY_DOCS)
    result = sklearn_loglikelihood_search(
        dtm, k_range=[2, 3, 4], params={"test": "sklearn-search-niter"}, n_iter=2, seed=1,
    )

    assert len(result) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_sklearn_corpus'`

- [ ] **Step 3: Write minimal implementation**

Add to `measurement/topic_modeling_lib.py`:

```python
import numpy as np
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split


def build_sklearn_corpus(tokenized_docs: list[list[str]]):
    """Reuses the already-tokenized/lemmatized docs from make_spacy_preprocessor -- the
    vectorizer's analyzer is the identity function, it does no tokenization of its own."""
    vectorizer = CountVectorizer(analyzer=lambda tokens: tokens)
    dtm = vectorizer.fit_transform(tokenized_docs)
    return vectorizer, dtm


def sklearn_loglikelihood_search(
    dtm,
    k_range: list[int],
    params: dict,
    n_iter: int | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Random search over k_range, each k scored by held-out log-likelihood (sklearn's
    LatentDirichletAllocation.score() on a 20% validation split) -- the approach from the
    linked practical guide, run alongside (not instead of) gensim_coherence_scan's coherence
    approach so the two can be compared."""
    cache_params = {**params, "method": "sklearn", "k_range": list(k_range), "n_iter": n_iter}
    cached = load_cache(cache_params, suffix=".pkl")
    if cached is not None:
        return cached

    train_dtm, val_dtm = train_test_split(dtm, test_size=0.2, random_state=seed)

    rng = np.random.default_rng(seed)
    n_iter = len(k_range) if n_iter is None else min(n_iter, len(k_range))
    tried_ks = rng.choice(k_range, size=n_iter, replace=False)

    rows = []
    for k in tried_ks:
        start = time.perf_counter()
        model = LatentDirichletAllocation(n_components=int(k), random_state=seed)
        model.fit(train_dtm)
        score = model.score(val_dtm)
        elapsed = time.perf_counter() - start
        print(f"[sklearn k={k}] {elapsed:.2f}s, log_likelihood={score:.2f}")
        rows.append({"k": int(k), "log_likelihood": score, "seconds": elapsed, "model": model})

    result = pd.DataFrame(rows)
    save_cache(result, cache_params, suffix=".pkl")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd measurement && ../topic_modeling_env/bin/python -m pytest test_topic_modeling_lib.py -v`
Expected: 18 passed

- [ ] **Step 5: Commit**

```bash
git add measurement/topic_modeling_lib.py measurement/test_topic_modeling_lib.py
git commit -m "Add sklearn log-likelihood random search with caching"
```

---

### Task 11: `measurement/topic_modeling.ipynb` — thin driver notebook

**Files:**
- Create: `measurement/topic_modeling.ipynb`

**Interfaces:**
- Consumes: every function from `measurement/topic_modeling_lib.py` (Tasks 5-10):
  `load_corpus`, `make_spacy_preprocessor`, `timed`, `build_gensim_corpus`,
  `gensim_coherence_scan`, `build_sklearn_corpus`, `sklearn_loglikelihood_search`.
- Produces: nothing further downstream in this plan — this is the terminal, exploratory
  artifact. Its printed timing log is what informs the (separately decided, out-of-scope-for-
  this-plan) full-corpus run.

- [ ] **Step 1: Create the notebook with the following cells**

Build it with `nbformat` (`topic_modeling_env/bin/python`, since `jupyter`/`nbformat` are
installed there) rather than hand-writing JSON, and set the kernelspec explicitly to the venv
registered in Task 1 so opening the notebook directly in Jupyter also uses the right
interpreter:

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb["metadata"]["kernelspec"] = {
    "name": "topic_modeling_env",
    "display_name": "topic_modeling_env (py3.11)",
    "language": "python",
}
nb["cells"] = [
    # markdown cells: nbf.v4.new_markdown_cell("...")
    # code cells: nbf.v4.new_code_cell("...")
    # in the order given below
]
with open("measurement/topic_modeling.ipynb", "w") as f:
    nbf.write(nb, f)
```

Cell 1 (markdown):
```markdown
# Topic modeling (LDA) — exploratory pass

Explores what policy topics are discussed in state-parliament speeches, scoped to each state's
legislative period immediately before vs. after AfD entry. This does not measure morality or
politeness — the topic assigned to each speech is meant as a **control** variable for later
analysis (some topics may be more polarized/moralized than others, independent of AfD entry).

Runs two independent topic-count-selection methods and compares them: gensim LDA scored by c_v
coherence, and sklearn LDA scored by held-out log-likelihood (the latter per the practical guide
https://medium.com/data-science/practical-guide-to-topic-modeling-with-lda-05cd6b027bdf, which
argues coherence is unreliable for tuning -- rather than pick a side, both run and get compared).

See `docs/superpowers/specs/2026-08-14-topic-modeling-lda-design.md` (local-only, not tracked in
git) for full design rationale.
```

Cell 2 (code — setup):
```python
import os
import sys
import time

import spacy
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(".."))
load_dotenv("../.env")

from topic_modeling_lib import (
    build_gensim_corpus,
    build_sklearn_corpus,
    gensim_coherence_scan,
    load_corpus,
    make_spacy_preprocessor,
    sklearn_loglikelihood_search,
    timed,
)

DATA_ROOT = os.environ["DATA_ROOT"]
timing_log = []
```

Cell 3 (markdown):
```markdown
## Parameters

Start small (single state, sampled) to get a fast timing read before scaling up -- see the
"Timing" cell at the end for what that read implies about a full run.
```

Cell 4 (code — parameters, the "different dataset inputs and sizes" knobs):
```python
STATES = ["by"]       # None = all 16 states
PRE_POST = None        # "pre", "post", or None for both
SAMPLE_N = 2000         # None = use every speech in scope
K_RANGE = [5, 10, 15, 20, 25, 30]
SKLEARN_N_ITER = 6      # None = try every k in K_RANGE

run_params = {
    "states": STATES,
    "pre_post": PRE_POST,
    "sample_n": SAMPLE_N,
    "preprocessing": "spacy_de_core_news_lg_v1",
}
```

Cell 5 (code — load + preprocess):
```python
with timed("load_corpus", log=timing_log):
    corpus_df = load_corpus(DATA_ROOT, states=STATES, pre_post=PRE_POST, sample_n=SAMPLE_N)
print(f"{len(corpus_df):,} documents loaded")

with timed("load spaCy model", log=timing_log):
    nlp = spacy.load("de_core_news_lg")
preprocess = make_spacy_preprocessor(nlp)

with timed("preprocess", log=timing_log):
    tokenized_docs = preprocess(corpus_df["text"].tolist())
print(f"Example tokens: {tokenized_docs[0][:10]}")
```

Cell 6 (markdown):
```markdown
## Vectorize and fit both models across K

Both methods share the same `tokenized_docs` and `K_RANGE`, but vectorize independently (gensim's
`Dictionary`/BoW vs. sklearn's `CountVectorizer`/doc-term matrix) since each library needs its own
input format. Results are cached under `measurement/run_history/topic_modeling/`, keyed by
`run_params` + K range + method -- rerunning this notebook with the same parameters loads from
disk instead of re-fitting.
```

Cell 7 (code — gensim):
```python
with timed("build_gensim_corpus", log=timing_log):
    dictionary, gensim_corpus = build_gensim_corpus(tokenized_docs)

with timed("gensim_coherence_scan (all k)", log=timing_log):
    gensim_results = gensim_coherence_scan(
        tokenized_docs, dictionary, gensim_corpus, k_range=K_RANGE, params=run_params,
    )
gensim_results[["k", "coherence", "seconds"]]
```

Cell 8 (code — sklearn):
```python
with timed("build_sklearn_corpus", log=timing_log):
    vectorizer, dtm = build_sklearn_corpus(tokenized_docs)

with timed("sklearn_loglikelihood_search (all k)", log=timing_log):
    sklearn_results = sklearn_loglikelihood_search(
        dtm, k_range=K_RANGE, params=run_params, n_iter=SKLEARN_N_ITER,
    )
sklearn_results[["k", "log_likelihood", "seconds"]]
```

Cell 9 (markdown):
```markdown
## Compare the two methods' preferred K
```

Cell 10 (code — comparison):
```python
best_gensim_k = int(gensim_results.loc[gensim_results["coherence"].idxmax(), "k"])
best_sklearn_k = int(sklearn_results.loc[sklearn_results["log_likelihood"].idxmax(), "k"])
print(f"gensim (c_v coherence) prefers k={best_gensim_k}")
print(f"sklearn (log-likelihood) prefers k={best_sklearn_k}")
print("Agreement" if best_gensim_k == best_sklearn_k else "Disagreement -- inspect both before picking K")
```

Cell 11 (markdown):
```markdown
## Inspect topics for the chosen K
```

Cell 12 (code — topic inspection, using whichever K was picked from the comparison above):
```python
chosen_k = best_gensim_k  # change after inspecting the comparison above
chosen_model = gensim_results.set_index("k").loc[chosen_k, "model"]

for topic_id, terms in chosen_model.print_topics(num_words=10):
    print(f"Topic {topic_id}: {terms}\n")
```

Cell 13 (markdown):
```markdown
## Timing summary — for estimating full-corpus runtime

This ran on the sample size and state(s) set in the Parameters cell above. Multiply the
preprocess/vectorize/fit seconds-per-document by the full pre/post-AfD corpus size (see
`preprocessing/afd_period_window.py`'s printed document count) to estimate a full run's cost
before committing to it.
```

Cell 14 (code — timing table):
```python
import pandas as pd

timing_df = pd.DataFrame(timing_log)
timing_df["seconds_per_doc"] = timing_df["seconds"] / len(corpus_df)
timing_df
```

- [ ] **Step 2: Run the notebook top to bottom**

Run: `topic_modeling_env/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=topic_modeling_env measurement/topic_modeling.ipynb`
Expected: exits 0, no cell raises an exception. (First run downloads/fits real models against a
2,000-document sample from Bayern — expect this to take a few minutes, not seconds; that's the
timing data the notebook itself is designed to capture.)

- [ ] **Step 3: Visually confirm the output**

Open the executed notebook and confirm: `run_params` prints sensible values, both
`gensim_results` and `sklearn_results` tables have 6 rows (or `SKLEARN_N_ITER` rows) with
non-null scores, the comparison cell prints either "Agreement" or "Disagreement", the topic
inspection cell prints 6 topics with plausible-looking German terms (not garbage tokens), and the
timing table has a `seconds_per_doc` column with reasonable (non-zero, non-huge) values.

- [ ] **Step 4: Commit**

```bash
git add measurement/topic_modeling.ipynb
git commit -m "Add topic_modeling.ipynb driver notebook"
```

---

## Explicitly out of scope for this plan

Matches the design spec's "out of scope" section:
- Keyword-assisted/seeded LDA
- `preText`-style preprocessing robustness comparison (would be a separate R script if built)
- A full multi-state, full-window production run (this plan's notebook runs on a sample; the
  timing log it produces is meant to inform that decision, not make it)
- Using the topic output as an actual control variable in a DiD/regression model (that's
  `analysis/`'s job, downstream of this plan)
