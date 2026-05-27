Added an ASV performance benchmark suite (demo experiment performance tests
and serialize/deserialize micro-benchmarks). A CI job publishes rendered
graphs to GitLab Pages alongside the docs, and an `asv_regression` job fails a
merge request when `asv continuous` finds a significant regression between its
merge base and branch tip.
