# ASV benchmark tiers

PsyNet splits ASV benchmarks into two CI tiers:

- `function_benchmarks.py` contains fast hot-path benchmarks selected by the
  merge-request regression gate.
- `experiment_performance.py` contains slow end-to-end experiment benchmarks
  that run on default-branch commits and feed the published benchmark log.
