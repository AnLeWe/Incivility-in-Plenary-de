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
