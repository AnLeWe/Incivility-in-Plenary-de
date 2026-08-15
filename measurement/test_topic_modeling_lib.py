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
