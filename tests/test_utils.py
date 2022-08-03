from math import isnan

import pytest
from mock import patch

from psynet.timeline import Module
from psynet.utils import DuplicateKeyError, corr, linspace, merge_dicts, organize_by_key


def test_linspace():
    assert linspace(0, 5, 6) == [0, 1, 2, 3, 4, 5]
    assert linspace(-1, 1, 5) == [-1, -0.5, 0, 0.5, 1]


def test_merge_dicts():
    x = {"a": 1, "b": 2, "c": 3}
    y = {"b": 5, "c": 4, "d": 11}
    z = {"c": 10, "d": -5, "e": 5}

    assert merge_dicts(x, y, z, overwrite=True) == {
        "a": 1,
        "b": 5,
        "c": 10,
        "d": -5,
        "e": 5,
    }

    with pytest.raises(DuplicateKeyError):
        merge_dicts(x, y, z, overwrite=False)


def test_corr():
    x = [1, 5, 2, 6, 8]
    y = [2, 7, 3, 4, 5]
    assert corr(x, y) == pytest.approx(0.658647361238887)

    x = [1, 1]
    y = [1, 1]
    assert isnan(corr(x, y))


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_min(mock_started_and_finished_times):
    started_and_finished_times = [
        {
            "time_started": "2020-08-26T22:34:58.333641",
            "time_finished": "2020-08-26T22:35:16.742562",
        },
        {
            "time_started": "2020-08-26T22:35:16.742562",
            "time_finished": "2020-08-26T22:37:35.132272",
        },
        {
            "time_started": "2020-08-26T22:36:22.188457",
            "time_finished": "2020-08-26T22:37:51.007836",
        },
        {
            "time_started": "2020-08-26T22:37:21.643429",
            "time_finished": "2020-08-26T23:59:28.508135",
        },
    ]
    mock_started_and_finished_times.return_value = started_and_finished_times
    assert Module.median_finish_time_in_min("participants", "module_id") == 1.893409075


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_min_incomplete_none(mock_started_and_finished_times):
    started_and_finished_times = [
        {"time_started": "2020-08-26T22:34:58.333641", "time_finished": None}
    ]
    mock_started_and_finished_times.return_value = started_and_finished_times
    assert Module.median_finish_time_in_min("participants", "module_id") is None


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_min_incomplete_blank(mock_started_and_finished_times):
    started_and_finished_times = [
        {"time_started": "2020-08-26T22:34:58.333641", "time_finished": ""}
    ]
    mock_started_and_finished_times.return_value = started_and_finished_times
    assert Module.median_finish_time_in_min("participants", "module_id") is None


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_min_incomplete_empty(mock_started_and_finished_times):
    mock_started_and_finished_times.return_value = []
    assert (
        Module.median_finish_time_in_min("started_and_finished_times", "module_id")
        is None
    )


def test_organize_by_key():
    assert organize_by_key(
        [["a", 3], ["b", 7], ["a", 1], ["b", 9]],
        key=lambda x: x[0],
    ) == {
        "a": [["a", 3], ["a", 1]],
        "b": [["b", 7], ["b", 9]],
    }
