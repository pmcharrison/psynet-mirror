# ASV benchmark tiers

PsyNet splits ASV benchmarks into two CI tiers by directory:

- `fast/` contains hot-path benchmarks selected by the merge-request regression
  gate with `--bench "^fast\\."`.
- `slow/` contains end-to-end experiment benchmarks
  that run on default-branch commits and feed the published benchmark log.

Default-branch CI runs the full ASV suite with `asv continuous`, so both tiers
contribute to regression checks on `master`.
