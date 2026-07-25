"""End-to-end benchmarks for local debug startup."""

import os
import random
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


_STATIC_FILE_PROFILES = {
    "baseline": (0, 0),
    "many_small_files": (50_000, 1),
    "few_large_files": (25, 4 * 1024 * 1024),
}


@contextmanager
def _temporary_static_payload(experiment_dir, count, file_size):
    """Create deterministic static files for the duration of a benchmark."""
    static_dir = Path(experiment_dir) / "static"
    static_dir_existed = static_dir.exists()
    payload_dir = None

    try:
        if count:
            static_dir.mkdir(parents=True, exist_ok=True)
            payload_dir = Path(
                tempfile.mkdtemp(prefix="asv-generated-", dir=static_dir)
            )
            contents = random.Random(0).randbytes(file_size)
            for index in range(count):
                (payload_dir / f"file-{index:05d}.bin").write_bytes(contents)
        yield payload_dir
    finally:
        if payload_dir is not None:
            shutil.rmtree(payload_dir)
        if not static_dir_existed and static_dir.exists():
            static_dir.rmdir()


class StaticFilesDebugLaunch:
    """Benchmark debug launch with representative static-file payloads."""

    params = list(_STATIC_FILE_PROFILES)
    param_names = ["profile"]
    timeout = 180
    version = 1

    def setup_cache(self):
        """Launch the static_big experiment once for each file profile."""
        from psynet.command_line import (
            _start_local_server_and_wait_for_ready,
            _stop_server,
        )

        repo_root = Path(__file__).parents[2]
        demo_dir = repo_root / "tests/experiments/static_big"
        original_directory = Path.cwd()
        results = {}

        try:
            os.chdir(demo_dir)
            for profile, (count, file_size) in _STATIC_FILE_PROFILES.items():
                server_info = None
                with _temporary_static_payload(demo_dir, count, file_size):
                    started_at = time.perf_counter()
                    try:
                        server_info = _start_local_server_and_wait_for_ready(
                            ["debug", "local"]
                        )
                        results[profile] = time.perf_counter() - started_at
                    finally:
                        if server_info is not None:
                            _stop_server(server_info)
        finally:
            os.chdir(original_directory)

        return results

    def track_launch_time_s(self, results, profile):
        """Return launch time for one static-file profile."""
        return results[profile]

    track_launch_time_s.unit = "s"
    track_launch_time_s.pretty_name = "Static files debug launch time"
