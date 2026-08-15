import pandas as pd

from afd_period_window import derive_period_windows, build_speech_documents


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
