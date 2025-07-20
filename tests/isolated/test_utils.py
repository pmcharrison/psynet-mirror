import logging
import os
import subprocess
import tempfile
from datetime import datetime
from math import isnan

import pytest
from mock import patch

from psynet.timeline import Module
from psynet.utils import (
    DuplicateKeyError,
    check_todos_before_deployment,
    corr,
    get_folder_size_mb,
    get_package_name,
    get_package_source_directory,
    get_psynet_root,
    git_repository_available,
    linspace,
    list_experiment_dirs,
    list_isolated_tests,
    logger,
    make_parents,
    merge_dicts,
    organize_by_key,
    safe,
    working_directory,
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


def test_demo_dirs():
    psynet_root = get_psynet_root()
    dirs = list_experiment_dirs()
    assert psynet_root.joinpath("demos/experiments/mcmcp").__str__() in dirs
    assert (
        psynet_root.joinpath("tests/experiments/recruiters/cap_recruiter").__str__()
        in dirs
    )

    dirs = list_experiment_dirs(for_ci_tests=True)
    assert psynet_root.joinpath("demos/experiments/mcmcp").__str__() in dirs
    assert (
        psynet_root.joinpath("tests/experiments/recruiters/cap_recruiter").__str__()
        not in dirs
    )


def test_isolated_tests():
    psynet_root = get_psynet_root()
    tests = list_isolated_tests()

    assert (
        psynet_root.joinpath(
            "tests/isolated/experiments/test_experiment_timeline.py"
        ).__str__()
        in tests
    )


def test_check_todos_before_deployment_raise():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            with open("file1.py", "w") as file:
                file.write("# TODO (1) line with a Python comment")
                file.flush()

            with open("file2.py", "w") as file:
                file.write("# TODO (2) line with a Python comment\n")
                file.write("// TODO (3) line with a JavaScript comment")
                file.flush()

            os.mkdir("subdir")
            with open("subdir/file.js", "w") as file:
                file.write("// TODO (4) line with a JavaScript comment\n")
                file.write("// TODO (5) line with a second JavaScript comment")
                file.flush()

            with open("subdir/file.html", "w") as file:
                file.write("// TODO (6) line with a JavaScript comment")
                file.flush()

            with pytest.raises(
                AssertionError,
                match="You have 6 TODOs in 4 file\\(s\\) in your experiment folder. "
                "Please fix them or remove them before deploying. To view all "
                "TODOs in your project in PyCharm, go to 'View' > 'Tool Windows' > 'TODO'. "
                "You can skip this check by writing `export SKIP_TODO_CHECK=1` "
                "\\(without quotes\\) in your terminal.",
            ):
                check_todos_before_deployment()


def test_check_todos_before_deployment_no_raise():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            with open("no_raise.py", "w") as file:
                file.write("# FIXME line with unrecognized")
                file.flush()

            with open("no_raise.txt", "w") as file:
                file.write("# TODO line in a file with unsupported file extension")
                file.flush()

            try:
                check_todos_before_deployment()
            except AssertionError:
                assert False


def test_get_folder_size_mb():
    with tempfile.TemporaryDirectory() as tempdir:
        subdir = os.path.join(tempdir, "subdir")
        os.mkdir(subdir)

        file1_path = os.path.join(tempdir, "file1.txt")
        file2_path = os.path.join(subdir, "file2.txt")

        with open(file1_path, "w") as file1:
            file1.write("a" * 1024 * 1024)  # 1 MB

        with open(file2_path, "w") as file2:
            file2.write("b" * 512 * 1024)  # 0.5 MB

        assert get_folder_size_mb(tempdir) == pytest.approx(1.5, rel=1e-2)
        assert get_folder_size_mb(subdir) == pytest.approx(0.5, rel=1e-2)


@pytest.fixture
def temp_package_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        with working_directory(tempdir):
            yield tempdir


@pytest.fixture
def pyproject_package(temp_package_dir):
    with open("pyproject.toml", "w") as f:
        f.write(
            """
[project]
name = "test-package"
"""
        )
    return "test-package"


@pytest.fixture
def setup_package(temp_package_dir):
    with open("setup.py", "w") as f:
        f.write(
            """
from setuptools import setup

setup(
    name="test-package",
    version="0.1",
)
"""
        )
    return "test-package"


def test_get_package_name_from_pyproject(pyproject_package):
    assert get_package_name() == pyproject_package


def test_get_package_name_from_setup(setup_package):
    assert get_package_name() == setup_package


def test_get_psynet_package_name():
    psynet_root = get_psynet_root()
    with working_directory(psynet_root):
        assert get_package_name() == "psynet"


def test_get_psynet_package_source_directory():
    """
    Test that get_package_source_directory works correctly for the psynet package.
    """
    psynet_root = get_psynet_root()
    with working_directory(psynet_root):
        source_dir = get_package_source_directory()
        assert source_dir == "psynet"
        assert os.path.isdir(source_dir)


# def test_get_package_name(temp_package_dir):
#     # Test with pyproject.toml
#     with open("pyproject.toml", "w") as f:
#         f.write("""
# [project]
# name = "test-package-1"
# """)
#     assert get_package_name() == "test-package-1"

#     # Test with setup.py
#     os.remove("pyproject.toml")
#     with open("setup.py", "w") as f:
#         f.write("""
# from setuptools import setup

# setup(
#     name="test-package-2",
#     version="0.1",
# )
# """)
#     assert get_package_name() == "test-package-2"

#     # Test with no config files
#     os.remove("setup.py")
#     with pytest.raises(FileNotFoundError, match="Could not find pyproject.toml or setup.py in current directory"):
#         get_package_name()


def test_git_repository_available_true(tmp_path):
    # Create a temporary directory and initialize a git repo
    with working_directory(tmp_path):
        subprocess.run(["git", "init"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert git_repository_available() is True


def test_git_repository_available_false(tmp_path):
    # Use a fresh temporary directory with no git repo
    with working_directory(tmp_path):
        assert git_repository_available() is False


def test_safe_decorator(caplog):
    @safe
    def no_error(x):
        return x * 2

    @safe
    def with_error(x):
        raise ValueError(f"bad value: {x}")

    # Normal case: should return correct value
    assert no_error(3) == 6

    # Exception case: should return None and log error
    with caplog.at_level(logging.ERROR, logger.name):
        result = with_error(5)
    assert result is None
    assert any(
        "Error in with_error: bad value: 5" in record.message
        and record.levelname == "ERROR"
        for record in caplog.records
    )
    # Should also include traceback
    assert any(
        "Traceback" in record.getMessage() or record.exc_info
        for record in caplog.records
    )


def test_safe_as_function_wrapper(caplog):
    def no_error(x):
        return x + 10

    def with_error(x):
        raise RuntimeError(f"fail: {x}")

    # Normal case
    assert safe(no_error)(5) == 15

    # Exception case
    with caplog.at_level(logging.ERROR, logger.name):
        result = safe(with_error)(7)
    assert result is None
    assert any(
        "Error in with_error: fail: 7" in record.message and record.levelname == "ERROR"
        for record in caplog.records
    )
    assert any(
        "Traceback" in record.getMessage() or record.exc_info
        for record in caplog.records
    )
