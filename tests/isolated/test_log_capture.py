import re
import time

import pexpect
import pytest
import requests

from psynet.pytest_psynet import path_to_test_experiment
from psynet.redis import redis_vars
from psynet.utils import get_experiment_url

LOG_PREFIX = "LOG_CAPTURE"

LEVELS = ("info", "warning", "error", "critical", "exception")

RUN_ID_KEY = "log_capture_run_id"
WORKER_DONE_KEY = "log_capture_worker_done"
CLOCK_DONE_KEY = "log_capture_clock_done"
EXPERIMENT_DONE_KEY = "log_capture_experiment_done"


def _marker(stage, process, level, run_id):
    return f"{LOG_PREFIX}|run={run_id}|stage={stage}|process={process}|level={level}"


def _get_run_id(timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run_id = redis_vars.get(RUN_ID_KEY, None)
        if run_id:
            return run_id
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for log capture run id")


def _assert_markers(output, process_label, stage, process, run_id):
    missing = []
    for level in LEVELS:
        marker = _marker(stage, process, level, run_id)
        pattern = re.compile(rf"{re.escape(process_label)}.*{re.escape(marker)}")
        if not pattern.search(output):
            missing.append(marker)
    if missing:
        raise AssertionError(
            "Missing log markers for stage " f"{stage} process {process}: {missing}"
        )


def _expect_all_markers(process, run_id, timeout=20):
    marker_map = {}
    expected = {
        ("experiment", "web"): set(LEVELS),
        ("async", "worker"): set(LEVELS),
        ("scheduled", "clock"): set(LEVELS),
    }
    process_labels = {
        "web": "web.1",
        "worker": "worker.1",
        "clock": "clock.1",
    }
    for (stage, process_name), levels in expected.items():
        run_ids = [run_id]
        if process_name == "clock":
            run_ids.append("unknown")
        for marker_run_id in run_ids:
            for level in levels:
                marker = _marker(stage, process_name, level, marker_run_id)
                marker_map[marker] = (stage, process_name, level)
    marker_pattern = "|".join(map(re.escape, marker_map))
    pattern = re.compile(rf"(web\.1|worker\.1|clock\.1).*({marker_pattern})")
    deadline = time.monotonic() + timeout
    while any(expected.values()) and time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            process.expect(pattern, timeout=remaining)
        except pexpect.TIMEOUT:
            break
        matched_label = process.match.group(1)
        matched_marker = process.match.group(2)
        info = marker_map.get(matched_marker)
        if not info:
            continue
        stage, process_name, level = info
        if process_labels[process_name] != matched_label:
            continue
        expected[(stage, process_name)].discard(level)
    missing = {key: sorted(levels) for key, levels in expected.items() if levels}
    if missing:
        raise AssertionError(f"Missing log markers: {missing}")


def _collect_output(process, condition=None, timeout=30):
    output = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        old_timeout = process.timeout
        process.timeout = 0.5
        try:
            chunk = process.read(1000000)
        except pexpect.TIMEOUT:
            chunk = process.before
        except pexpect.EOF:
            chunk = process.before
        finally:
            process.timeout = old_timeout
        if chunk:
            output.append(chunk)
            if isinstance(chunk, str):
                process.before = ""
        if condition and condition():
            break
        time.sleep(0.1)
    if condition and not condition():
        raise AssertionError("Timed out waiting for log capture tasks to finish")
    return "".join(output)


def _wait_for_async_logs(run_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (
            redis_vars.get(EXPERIMENT_DONE_KEY, None) == run_id
            and redis_vars.get(WORKER_DONE_KEY, None) == run_id
            and redis_vars.get(CLOCK_DONE_KEY, None) in {run_id, "unknown"}
        ):
            return
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for log capture tasks to finish")


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("log_capture")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestLogCapture:
    def test_log_capture(self, debug_experiment):
        launch_output = debug_experiment.before or ""
        launch_output += _collect_output(debug_experiment, timeout=5)
        run_id = _get_run_id()
        _assert_markers(launch_output, "web.1", "launch", "web", run_id)

        base_url = get_experiment_url()
        assert base_url, "Experiment base URL was not set"
        response = requests.post(f"{base_url}/log_capture", timeout=10)
        response.raise_for_status()

        _wait_for_async_logs(run_id, timeout=30)
        _expect_all_markers(debug_experiment, run_id)
