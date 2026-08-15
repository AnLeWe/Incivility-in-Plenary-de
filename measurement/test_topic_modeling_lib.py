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
