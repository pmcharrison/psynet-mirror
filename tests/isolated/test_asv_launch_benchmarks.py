from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.slow.experiment_launch import StaticBigLaunch, time_experiment_launch


def test_static_big_launch_tracks_launch_time_seconds():
    benchmark = StaticBigLaunch()
    data = {"launch_seconds": 12.5}

    assert benchmark.track_launch_time_s(data) == 12.5
    assert benchmark.track_launch_time_s.unit == "s"
    assert benchmark.track_launch_time_s.pretty_name == "static_big Launch time"


def test_time_experiment_launch_returns_elapsed_seconds_on_ready_phrase(tmp_path):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()

    process = MagicMock()
    process.pid = 12345
    process.poll.return_value = None
    process.stdout = MagicMock()
    process.stdout.readline.side_effect = [
        "starting...\n",
        "Experiment launch complete!\n",
    ]

    with (
        patch(
            "benchmarks.slow.experiment_launch.subprocess.Popen", return_value=process
        ) as popen,
        patch("benchmarks.slow.experiment_launch._terminate_process") as terminate,
        patch(
            "benchmarks.slow.experiment_launch.time.perf_counter", side_effect=[100.0, 112.5]
        ),
        patch("benchmarks.slow.experiment_launch.time.monotonic", return_value=0.0),
    ):
        elapsed = time_experiment_launch(demo_dir, max_wait=30.0)

    assert elapsed == 12.5
    popen.assert_called_once()
    assert popen.call_args.kwargs["cwd"] == str(demo_dir)
    assert popen.call_args.args[0][:3] == ["psynet", "debug", "local"]
    terminate.assert_called_once_with(process)


def test_time_experiment_launch_retries_without_legacy_when_heroku_missing(tmp_path):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()

    first = MagicMock()
    first.pid = 1
    first.poll.return_value = 1
    first.stdout = MagicMock()
    first.stdout.readline.side_effect = [
        "No such file or directory: 'heroku'\n",
        "",
    ]

    second = MagicMock()
    second.pid = 2
    second.poll.return_value = None
    second.stdout = MagicMock()
    second.stdout.readline.side_effect = [
        "Experiment launch complete!\n",
    ]

    with (
        patch(
            "benchmarks.slow.experiment_launch.subprocess.Popen",
            side_effect=[first, second],
        ) as popen,
        patch("benchmarks.slow.experiment_launch._terminate_process"),
        patch(
            "benchmarks.slow.experiment_launch.time.perf_counter",
            side_effect=[10.0, 20.0, 31.0],
        ),
        patch("benchmarks.slow.experiment_launch.time.monotonic", return_value=0.0),
    ):
        elapsed = time_experiment_launch(demo_dir, max_wait=30.0)

    assert elapsed == 11.0
    assert popen.call_count == 2
    assert "--legacy" in popen.call_args_list[0].args[0]
    assert "--legacy" not in popen.call_args_list[1].args[0]


def test_time_experiment_launch_raises_when_ready_phrase_never_appears(tmp_path):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()

    process = MagicMock()
    process.pid = 99
    process.poll.return_value = 1
    process.stdout = MagicMock()
    process.stdout.readline.side_effect = ["boom\n", ""]

    with (
        patch(
            "benchmarks.slow.experiment_launch.subprocess.Popen", return_value=process
        ),
        patch("benchmarks.slow.experiment_launch._terminate_process"),
        patch("benchmarks.slow.experiment_launch.time.perf_counter", return_value=0.0),
        patch("benchmarks.slow.experiment_launch.time.monotonic", return_value=0.0),
    ):
        with pytest.raises(RuntimeError, match="failed to launch"):
            time_experiment_launch(Path(demo_dir), max_wait=1.0)
