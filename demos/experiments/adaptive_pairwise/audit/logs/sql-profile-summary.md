# SQL profile summary

The profiler was enabled with call-site capture around otherwise equivalent
one-bot performance runs.

## Before preserving discovered networks

- 38,501 SQL statements and 32.16 seconds measured in SQL.
- Two network-loading statements each ran 16,719 times.
- Their call sites were `StaticTrialMaker._candidate_network` and the following
  asynchronous-state check in `_find_eligible_candidates`.
- The run completed one bot in 34.0 seconds. Median response latency was 0.127
  seconds and p95 was 1.553 seconds.

The repeated count equals the cumulative number of candidate pairs traversed
while assigning trials. Static discovery converted already-loaded networks to
nodes and then followed `node.network`; polymorphic relationship loading issued
two lazy queries for nearly every candidate.

## After preserving discovered networks

- 11,169 SQL statements and 7.80 seconds measured in SQL while completing seven
  bots in the same one-minute window.
- The two 16,719-query network-loading statements disappeared.
- Successful bots averaged 6.0 seconds. Median response latency was 0.122
  seconds and p95 was 0.136 seconds.

## Concurrent follow-up

A one-minute, 40-bot profiled run captured 589 statements slower than 5 ms,
totalling 7.63 seconds in SQL. The static candidate query ran 40 times and
averaged 6.34 ms, showing that SQL execution was no longer the main tail-latency
source.

The final unprofiled five-minute run completed 27 bots successfully, with 1,925
requests, median response latency 0.153 seconds, and p95 5.616 seconds. This is
a large improvement over zero completions and p95 23.3 seconds, but the tail
still exceeds the adaptive workflow's two-second threshold. Remaining work is
dominated by loading and deserializing the full 500-candidate ORM collection
and request queueing, not by the removed SQL N+1.

## Virtual-candidate follow-up

The worked experiment was subsequently converted from 500 static pair nodes to
runtime `Trial.cue` selection. Its export contains one generic node, 100 cached
item-level audio assets, and only the 80 delivered trials. Four concurrent bots
completed in 29.3 seconds with mean HTTP latency 0.256 seconds, compared with
about 89 seconds and 0.596 seconds for the static version.

At 40-way concurrency, median latency remained low at 0.259 seconds but p95 was
7.210 seconds. Pair discovery and its SQL N+1 are absent from this version;
future investigation should isolate request queueing and model-worker
contention.
