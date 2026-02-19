# Adaptive testing with catR

This demo shows how to call the R package `catR` from PsyNet using `rpy2`.

## Key files

- `prepare_docker_image.sh` installs R and the `catR` package.
- `requirements.txt` and `constraints.txt` include `rpy2`.
- `experiment.py` contains `run_catr_smoke_test()`, a minimal catR integration helper.

## Notes

- With Docker deployment (`psynet deploy` default), these dependencies are built into
  the experiment image.
- Without Docker, install R + catR on the deployment host and install Python
  dependencies (including `rpy2`) in the experiment environment.
