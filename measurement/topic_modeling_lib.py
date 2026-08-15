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

import joblib


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
