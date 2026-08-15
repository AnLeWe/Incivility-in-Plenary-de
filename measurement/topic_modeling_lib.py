"""Reusable functions for the exploratory LDA topic-modeling pipeline over
speeches_afd_prepost.parquet (built by preprocessing/afd_period_window.py). See
docs/superpowers/specs/2026-08-14-topic-modeling-lda-design.md (local-only) for the full design
rationale.
"""
import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

import joblib
import pandas as pd


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
            tokens = []
            for tok in doc:
                # Use lemma if available, otherwise use text (for blank models)
                token_value = tok.lemma_ if tok.lemma_ else tok.text
                if tok.is_alpha and not tok.is_stop and len(token_value) > 2:
                    tokens.append(token_value.lower())
            result.append(tokens)
        return result

    return _preprocess
