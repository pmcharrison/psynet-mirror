import os
import tempfile
from datetime import datetime
from math import isnan

import pytest
from mock import patch

from psynet.timeline import Module
from psynet.utils import (
    DuplicateKeyError,
    corr,
    linspace,
    make_parents,
    merge_dicts,
    organize_by_key,
)


def test_make_dirs():
    with tempfile.TemporaryDirectory() as tempdir:
        subdir = "abc123"
        path = os.path.join(tempdir, subdir, "test.txt")

        with pytest.raises(FileNotFoundError):
            with open(path, "w") as file:
                file.write("Test")

        with open(make_parents(path), "w") as file:
            file.write("Test")

        assert make_parents(path) == path


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
def test_median_finish_time_in_s(mock_started_and_finished_times):
    started_and_finished_times = [
        {
            "time_started": get_datetime("2020-08-26 22:34:58.333641"),
            "time_finished": get_datetime("2020-08-26 22:35:16.742562"),
        },
        {
            "time_started": get_datetime("2020-08-26 22:35:16.742562"),
            "time_finished": get_datetime("2020-08-26 22:37:35.132272"),
        },
        {
            "time_started": get_datetime("2020-08-26 22:36:22.188457"),
            "time_finished": get_datetime("2020-08-26 22:37:51.007836"),
        },
        {
            "time_started": get_datetime("2020-08-26 22:37:21.643429"),
            "time_finished": get_datetime("2020-08-26 23:59:28.508135"),
        },
    ]
    mock_started_and_finished_times.return_value = started_and_finished_times
    assert Module.median_finish_time_in_s("participants", "module_id") == 113.6045445


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_s_incomplete_none(mock_started_and_finished_times):
    started_and_finished_times = [
        {
            "time_started": get_datetime("2020-08-26 22:34:58.333641"),
            "time_finished": None,
        }
    ]
    mock_started_and_finished_times.return_value = started_and_finished_times
    assert Module.median_finish_time_in_s("participants", "module_id") is None


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_s_incomplete_blank(mock_started_and_finished_times):
    started_and_finished_times = [
        {
            "time_started": get_datetime("2020-08-26 22:34:58.333641"),
            "time_finished": "",
        }
    ]
    mock_started_and_finished_times.return_value = started_and_finished_times
    assert Module.median_finish_time_in_s("participants", "module_id") is None


@patch("psynet.timeline.Module.started_and_finished_times")
def test_median_finish_time_in_s_incomplete_empty(mock_started_and_finished_times):
    mock_started_and_finished_times.return_value = []
    assert (
        Module.median_finish_time_in_s("started_and_finished_times", "module_id")
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


def get_datetime(str):
    return datetime.strptime(str, "%Y-%m-%d %H:%M:%S.%f")
