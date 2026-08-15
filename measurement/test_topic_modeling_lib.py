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
