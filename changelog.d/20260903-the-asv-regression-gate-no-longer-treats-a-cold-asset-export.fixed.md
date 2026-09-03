The ``asv_regression`` merge-request gate no longer treats a cold asset-export
cache as a regression. Fast export benchmarks record a cache-warmed
``psynet export local --assets collected`` sample so ``asv continuous`` can
compare BASE and HEAD in either order. The fast gate also stops tracking noisy
warm-cache incremental hydrate timings while still validating warm cache reuse
during benchmark setup.
