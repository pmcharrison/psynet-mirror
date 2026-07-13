from pathlib import Path

import psynet.command_line
from benchmarks.slow.experiment_performance import (
    AsyncProcesses,
    Static,
    StaticBigLaunch,
)


def test_slow_asv_tracks_median_response_time():
    benchmark = Static()
    data = {
        (5, 2.0): {
            "median_response_time": 0.123,
        }
    }

    assert benchmark.track_median_response_time_ms(data, 5, 2.0) == 123.0


def test_slow_asv_tracks_median_queue_delay_for_async_experiment():
    benchmark = AsyncProcesses()
    data = {
        (5, 2.0): {
            "q_delay_median": 0.045,
        }
    }

    assert benchmark.track_median_queue_delay_ms(data, 5, 2.0) == 45.0


def test_slow_asv_no_longer_tracks_completion_window_metrics():
    benchmark = Static()

    assert not hasattr(benchmark, "track_failure_rate")
    assert not hasattr(benchmark, "track_incomplete_rate")
    assert not hasattr(benchmark, "track_sec_per_bot")


def test_static_big_launch_benchmark(monkeypatch):
    benchmark = StaticBigLaunch()
    original_directory = Path.cwd()
    server_info = {"process": object()}
    launched_from = None
    stopped_server = None

    def start_server():
        nonlocal launched_from
        launched_from = Path.cwd()
        return server_info

    def stop_server(info):
        nonlocal stopped_server
        stopped_server = info

    monkeypatch.setattr(
        psynet.command_line, "_start_local_server_and_wait_for_ready", start_server
    )
    monkeypatch.setattr(psynet.command_line, "_stop_server", stop_server)

    duration = benchmark.setup_cache()

    assert launched_from == original_directory / "tests/experiments/static_big"
    assert stopped_server is server_info
    assert Path.cwd() == original_directory
    assert benchmark.track_launch_time_s(duration) >= 0
