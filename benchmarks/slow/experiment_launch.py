"""
ASV benchmarks for experiment launch time.

Measures how long ``psynet debug local`` takes to reach
``Experiment launch complete!`` for selected demos. These are end-to-end
startup costs (import, DB setup, ``on_launch``), distinct from the load-test
metrics in ``experiment_performance``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


_READY_PHRASE = "Experiment launch complete!"
_LEGACY_FALLBACK_MARKER = "No such file or directory: 'heroku'"


def _terminate_process(process: subprocess.Popen) -> None:
    """Terminate a launched experiment server process and its children."""
    if process.poll() is not None:
        return

    pid = process.pid

    def _signal(sig: signal.Signals) -> None:
        try:
            os.killpg(os.getpgid(pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.send_signal(sig)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    _signal(signal.SIGINT)
    try:
        process.wait(timeout=15)
        return
    except subprocess.TimeoutExpired:
        pass

    _signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    _signal(signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def time_experiment_launch(demo_dir: Path, max_wait: float = 300.0) -> float:
    """
    Launch an experiment and return seconds until it reports ready.

    Parameters
    ----------
    demo_dir :
        Experiment directory containing ``experiment.py``.
    max_wait :
        Seconds to wait for ``Experiment launch complete!`` before failing.

    Returns
    -------
    float
        Elapsed wall-clock seconds from process start to the ready phrase.
    """
    env = os.environ.copy()
    env.setdefault("SKIP_DEPENDENCY_CHECK", "1")
    env.setdefault("BROWSER", "true")
    env["PYTHONUNBUFFERED"] = "1"

    start_commands = [
        ["psynet", "debug", "local", "--legacy", "--no-browsers"],
        ["psynet", "debug", "local"],
    ]
    last_output_lines: list[str] = []

    for command_args in start_commands:
        start = time.perf_counter()
        process = subprocess.Popen(
            command_args,
            cwd=str(demo_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        output_lines: list[str] = []
        try:
            deadline = time.monotonic() + max_wait
            assert process.stdout is not None
            while time.monotonic() < deadline:
                line = process.stdout.readline()
                if line:
                    output_lines.append(line.rstrip("\n"))
                    if _READY_PHRASE in line:
                        return time.perf_counter() - start
                elif process.poll() is not None:
                    break
                else:
                    time.sleep(0.05)

            last_output_lines = output_lines[-50:]
            if command_args == start_commands[0] and any(
                _LEGACY_FALLBACK_MARKER in line for line in last_output_lines
            ):
                continue

            tail = "\n".join(last_output_lines) if last_output_lines else "(no output)"
            raise RuntimeError(
                f"Experiment in {demo_dir} failed to launch within {max_wait}s.\n"
                f"Command: {' '.join(command_args)}\n"
                f"Last output:\n{tail}"
            )
        finally:
            _terminate_process(process)

    raise RuntimeError(f"Experiment in {demo_dir} failed to launch.")


class StaticBigLaunch:
    """
    Time taken to launch the ``static_big`` fixture experiment.

    ``static_big`` builds a large static trial graph (thousands of nodes), so
    launch duration is a useful regression signal for experiment startup cost.
    """

    timeout = 600

    # Explicit benchmark version; see
    # ``slow.experiment_performance._BaseExperiment``. Bump this integer when a
    # benchmark change makes new results incomparable to old ones.
    version = 1

    def setup_cache(self):
        repo_root = Path(__file__).parents[2]
        demo_dir = repo_root / "tests" / "experiments" / "static_big"
        return {"launch_seconds": time_experiment_launch(demo_dir)}

    def track_launch_time_s(self, data):
        return data["launch_seconds"]

    track_launch_time_s.unit = "s"
    track_launch_time_s.pretty_name = "static_big Launch time"
