import json
import subprocess
import tempfile
from pathlib import Path


class _BaseE2E:
    """Base class for end-to-end perf benchmarks of a single psynet demo.

    Subclasses set ``demo_name`` (the directory under ``demos/experiments/``)
    and may override ``params`` to change the n_bots sweep. ``setup_cache``
    runs ``psynet performance-test local`` once with the full sweep; track
    methods extract per-n_bots scalars from the cached JSON.
    """

    demo_name: str | None = None
    demo_root = "demos/experiments"
    params = [25]
    param_names = ["n_bots"]
    duration_minutes = 1.0
    timeout = 1800

    def setup_cache(self):
        if self.demo_name is None:
            raise NotImplementedError("subclass must set demo_name")

        repo_root = Path(__file__).parent.parent
        demo_dir = repo_root / self.demo_root / self.demo_name
        n_bots_arg = ",".join(str(n) for n in self.params)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name

        try:
            subprocess.run(
                [
                    "psynet",
                    "performance-test",
                    "local",
                    "--n-bots",
                    n_bots_arg,
                    "--duration-minutes",
                    str(self.duration_minutes),
                    "--json-output",
                    str(json_path),
                ],
                cwd=demo_dir,
                check=True,
            )
            with open(json_path) as fh:
                return json.load(fh)
        finally:
            Path(json_path).unlink(missing_ok=True)

    @staticmethod
    def _result_for(data, n_bots):
        return next(r for r in data["results"] if r["n_bots"] == n_bots)

    def track_requests_per_sec(self, data, n_bots):
        return self._result_for(data, n_bots)["requests_per_sec"]

    track_requests_per_sec.unit = "req/s"

    def track_p95_response_time_ms(self, data, n_bots):
        return self._result_for(data, n_bots)["p95_response_time"] * 1000.0

    track_p95_response_time_ms.unit = "ms"

    def track_bots_succeeded(self, data, n_bots):
        return self._result_for(data, n_bots)["bots_succeeded"]

    track_bots_succeeded.unit = "count"


class TimelineE2E(_BaseE2E):
    demo_name = "timeline"


class StaticE2E(_BaseE2E):
    demo_name = "static"


class StaticBigE2E(_BaseE2E):
    demo_name = "static_big"
    demo_root = "tests/experiments"
