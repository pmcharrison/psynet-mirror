# ASV benchmark tiers

PsyNet splits ASV benchmarks into two CI tiers by directory:

- `fast/` contains hot-path benchmarks selected by the merge-request regression
  gate with `--bench "^fast\\."`.
- `slow/` contains end-to-end experiment benchmarks
  that run on default-branch commits and feed the published benchmark log.
  These benchmarks track median request time, static_big launch time, plus
  median queue delay for an experiment that exercises async worker processes.

Default-branch CI runs the full ASV suite with `asv continuous`, so both tiers
contribute to regression checks on `master`.
