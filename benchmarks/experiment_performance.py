"""
ASV benchmarks for end-to-end experiment performance.

ASV discovers benchmark classes in this module via ``benchmark_dir`` in
``asv.conf.json``, and calls two kinds of methods:

- ``setup_cache()``: called once per class, runs all parameter combinations
  and returns a dict of results. ASV passes this dict as the first argument
  to every ``track_*`` call.
- ``track_*(data, *param_values)``: called once per parameter combination,
  extracts a single scalar metric from the cached results.

See https://asv.readthedocs.io/en/stable/writing_benchmarks.html
"""

import itertools
import json
import subprocess
import tempfile
from pathlib import Path


class _BaseExperiment:
    """
    Base class for end-to-end performance benchmarks of a single psynet demo.

    ``setup_cache`` invokes ``psynet performance-test local`` for each
    combination of ``params`` and stores the per-combination output in a dict
    keyed by parameter tuple (in ``param_names`` order). ``track_*`` methods
    then extract scalars (requests/sec, p95 response time, bots succeeded) per
    combination. Subclasses must set ``demo_name``; everything else has sensible
    defaults.

    Sweep axes (``param_names``) map to ``psynet performance-test local`` CLI
    flags by replacing underscores with dashes (e.g. ``"duration_minutes"`` →
    ``--duration-minutes``); any flag the CLI accepts is sweepable. Values not
    specified take the CLI default. Each Cartesian combination triggers one
    psynet invocation.

    Attributes
    ----------

    demo_name : str
        Directory name of the demo under ``demo_root``. Required.

    demo_root : str
        Path (relative to the repo root) of the demo tree containing
        ``demo_name``. Defaults to ``"demos/experiments"``; override to
        ``"tests/experiments"`` for fixture demos.

    params : list[list]
        ASV-style sweep, one inner list per axis. ``asv`` benchmarks every
        combination, producing one row per combination per ``track_*`` method.
        Defaults to a single a 5-minute test with a bot-count of 25: ``[[25],
        [5.0]]``. To sweep multiple bot counts: ``[[10, 25, 50], [5.0]]``. To also
        sweep duration: ``[[25], [1.0, 2.0]]`` (with ``param_names = ["n_bots",
        "duration_minutes"]``).

    param_names : list[str]
        Names for each axis of ``params``, in matching order. Each name is
        passed through to the corresponding ``psynet performance-test local``
        CLI flag (underscores → dashes). Defaults to ``["n_bots",
        "duration_minutes"]``. Track methods receive the per-combination values
        positionally via ``*param_values`` after the cached data.

    timeout : int
        Hard upper bound (seconds) for ``setup_cache`` before asv kills the run.
        Should accommodate the full Cartesian sweep, since ``setup_cache`` runs
        every combination before any ``track_*`` call. Defaults to ``1800``.
    """

    demo_name: str | None = None
    demo_root = "demos/experiments"
    params = [[25], [5.0]]
    param_names = ["n_bots", "duration_minutes"]
    timeout = 1800

    def setup_cache(self):
        if self.demo_name is None:
            raise NotImplementedError("subclass must set demo_name")

        repo_root = Path(__file__).parent.parent
        demo_dir = repo_root / self.demo_root / self.demo_name

        results = {}
        for combo in itertools.product(*self.params):
            flags = []
            for name, value in zip(self.param_names, combo):
                flags += [f"--{name.replace('_', '-')}", str(value)]

            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                json_path = f.name

            try:
                subprocess.run(
                    [
                        "psynet",
                        "performance-test",
                        "local",
                        *flags,
                        "--json-output",
                        str(json_path),
                    ],
                    cwd=demo_dir,
                    check=True,
                )
                with open(json_path) as fh:
                    output = json.load(fh)
            finally:
                Path(json_path).unlink(missing_ok=True)

            results[combo] = output["results"][0]

        return results

    @staticmethod
    def _result_for(data, *param_values):
        return data[tuple(param_values)]

    def track_requests_per_sec(self, data, *param_values):
        return self._result_for(data, *param_values)["requests_per_sec"]

    track_requests_per_sec.unit = "req/s"

    def track_p95_response_time_ms(self, data, *param_values):
        return self._result_for(data, *param_values)["p95_response_time"] * 1000.0

    track_p95_response_time_ms.unit = "ms"

    def track_bots_succeeded(self, data, *param_values):
        return self._result_for(data, *param_values)["bots_succeeded"]

    track_bots_succeeded.unit = "count"


class Timeline(_BaseExperiment):
    demo_name = "timeline"


class Static(_BaseExperiment):
    demo_name = "static"


class StaticBig(_BaseExperiment):
    demo_name = "static_big"
    demo_root = "tests/experiments"
