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
