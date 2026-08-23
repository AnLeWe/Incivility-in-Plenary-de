import time

from topic_modeling_lib import cache_key, load_cache, save_cache, timed


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


from topic_modeling_lib import (
    build_gensim_corpus,
    build_sklearn_corpus,
    sklearn_loglikelihood_search,
    sklearn_topic_coherence,
)


def test_build_sklearn_corpus_shapes():
    vectorizer, dtm = build_sklearn_corpus(_TOY_DOCS)

    assert dtm.shape[0] == len(_TOY_DOCS)
    assert len(vectorizer.vocabulary_) > 0


def test_sklearn_topic_coherence_returns_a_float():
    from sklearn.decomposition import LatentDirichletAllocation

    vectorizer, dtm = build_sklearn_corpus(_TOY_DOCS)
    dictionary, _ = build_gensim_corpus(_TOY_DOCS)
    model = LatentDirichletAllocation(n_components=2, random_state=42).fit(dtm)

    coherence = sklearn_topic_coherence(model, vectorizer, _TOY_DOCS, dictionary)

    assert isinstance(coherence, float)


def test_sklearn_loglikelihood_search_returns_one_row_per_k(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    vectorizer, dtm = build_sklearn_corpus(_TOY_DOCS)
    dictionary, _ = build_gensim_corpus(_TOY_DOCS)
    result = sklearn_loglikelihood_search(
        dtm, vectorizer, _TOY_DOCS, dictionary, k_range=[2, 3], params={"test": "sklearn-search"},
    )

    assert sorted(result["k"]) == [2, 3]
    assert (result["seconds"] >= 0).all()
    assert result["coherence"].notna().all()


def test_sklearn_loglikelihood_search_respects_n_iter(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    vectorizer, dtm = build_sklearn_corpus(_TOY_DOCS)
    dictionary, _ = build_gensim_corpus(_TOY_DOCS)
    result = sklearn_loglikelihood_search(
        dtm, vectorizer, _TOY_DOCS, dictionary,
        k_range=[2, 3, 4], params={"test": "sklearn-search-niter"}, n_iter=2, seed=1,
    )

    assert len(result) == 2


from topic_modeling_lib import _scan_cache_params


def test_scan_cache_params_key_differs_by_seed():
    a = cache_key(_scan_cache_params({"state": "by"}, "gensim", [5, 10], seed=1))
    b = cache_key(_scan_cache_params({"state": "by"}, "gensim", [5, 10], seed=2))

    assert a != b


def test_scan_cache_params_key_ignores_k_range_order():
    a = cache_key(_scan_cache_params({"state": "by"}, "gensim", [5, 10], seed=42))
    b = cache_key(_scan_cache_params({"state": "by"}, "gensim", [10, 5], seed=42))

    assert a == b


def test_scan_cache_params_key_differs_by_method():
    a = cache_key(_scan_cache_params({"state": "by"}, "gensim", [5], seed=42))
    b = cache_key(_scan_cache_params({"state": "by"}, "sklearn", [5], seed=42))

    assert a != b


def test_gensim_coherence_scan_writes_separate_cache_entry_per_seed(tmp_path, monkeypatch):
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    dictionary, corpus = build_gensim_corpus(_TOY_DOCS)
    params = {"test": "gensim-scan-seed"}
    gensim_coherence_scan(_TOY_DOCS, dictionary, corpus, k_range=[2], params=params, seed=1)
    gensim_coherence_scan(_TOY_DOCS, dictionary, corpus, k_range=[2], params=params, seed=2)

    assert len(list(tmp_path.glob("*.pkl"))) == 2


def test_sklearn_search_shares_cache_entry_for_equivalent_n_iter(tmp_path, monkeypatch):
    """n_iter=None and n_iter=len(k_range) are the same search, so they must share a key."""
    import topic_modeling_lib
    monkeypatch.setattr(topic_modeling_lib, "CACHE_DIR", tmp_path)

    vectorizer, dtm = build_sklearn_corpus(_TOY_DOCS)
    dictionary, _ = build_gensim_corpus(_TOY_DOCS)
    params = {"test": "sklearn-search-niter-clamp"}
    sklearn_loglikelihood_search(dtm, vectorizer, _TOY_DOCS, dictionary, k_range=[2, 3], params=params, n_iter=None)
    sklearn_loglikelihood_search(dtm, vectorizer, _TOY_DOCS, dictionary, k_range=[2, 3], params=params, n_iter=2)

    assert len(list(tmp_path.glob("*.pkl"))) == 1
