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

WORKER_DONE_KEY = "log_capture_worker_done"
CLOCK_DONE_KEY = "log_capture_clock_done"


def _marker(stage, process, level):
    return f"{LOG_PREFIX}|stage={stage}|process={process}|level={level}"


def _assert_markers(output, process_label, stage, process):
    missing = []
    for level in LEVELS:
        marker = _marker(stage, process, level)
        pattern = re.compile(rf"{re.escape(process_label)}.*{re.escape(marker)}")
        if not pattern.search(output):
            missing.append(marker)
    if missing:
        raise AssertionError(
            "Missing log markers for stage "
            f"{stage} process {process}: {missing}"
        )


def _collect_output(process, condition=None, timeout=30):
    output = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            while True:
                chunk = process.read_nonblocking(size=100000, timeout=0)
                if not chunk:
                    break
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8", errors="replace")
                output.append(chunk)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            break
        if condition and condition():
            break
        time.sleep(0.1)
    if condition and not condition():
        raise AssertionError("Timed out waiting for log capture tasks to finish")
    return "".join(output)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("log_capture")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestLogCapture:
    def test_log_capture(self, debug_experiment):
        launch_output = debug_experiment.before or ""
        _assert_markers(launch_output, "web.1", "launch", "web")

        base_url = get_experiment_url()
        assert base_url, "Experiment base URL was not set"
        response = requests.post(f"{base_url}/log_capture", timeout=10)
        response.raise_for_status()

        def _ready():
            return redis_vars.get(WORKER_DONE_KEY, False) and redis_vars.get(
                CLOCK_DONE_KEY, False
            )

        output_after = _collect_output(debug_experiment, condition=_ready, timeout=30)
        output_after += _collect_output(debug_experiment, timeout=2)

        _assert_markers(output_after, "web.1", "experiment", "web")
        _assert_markers(output_after, "worker.1", "async", "worker")
        _assert_markers(output_after, "clock.1", "scheduled", "clock")
