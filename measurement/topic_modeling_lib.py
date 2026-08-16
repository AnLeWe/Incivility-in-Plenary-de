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
import numpy as np
import pandas as pd
from gensim import corpora
from gensim.models import CoherenceModel, LdaModel
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split


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


def _scan_cache_params(
    params: dict, method: str, k_range: list[int], seed: int, **extra
) -> dict:
    """Builds the cache key inputs for a K-scan: everything that changes the result must be in
    here. `seed` changes which models get fit, so a different seed must miss the cache; `k_range`
    is sorted so that [5, 10] and [10, 5] -- the same set of K's, hence the same computation --
    share one entry. `extra` carries method-specific fields (e.g. sklearn's *effective*,
    post-clamp n_iter)."""
    return {**params, "method": method, "k_range": sorted(k_range), "seed": seed, **extra}


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
    params | {"method": "gensim", ...} (see _scan_cache_params) so re-running the notebook with
    unchanged params/k_range/seed loads from disk instead of re-fitting."""
    cache_params = _scan_cache_params(params, "gensim", k_range, seed)
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
    approach so the two can be compared.

    k_range is sorted before sampling from it so that the K's actually tried depend only on the
    *set* of K's requested, matching the cache key built from the same sorted list. n_iter enters
    the cache key clamped (its effective value), so n_iter=None and n_iter=len(k_range) -- the
    same search -- share one cache entry."""
    k_range = sorted(k_range)
    n_iter = len(k_range) if n_iter is None else min(n_iter, len(k_range))

    cache_params = _scan_cache_params(params, "sklearn", k_range, seed, n_iter=n_iter)
    cached = load_cache(cache_params, suffix=".pkl")
    if cached is not None:
        return cached

    train_dtm, val_dtm = train_test_split(dtm, test_size=0.2, random_state=seed)

    rng = np.random.default_rng(seed)
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
