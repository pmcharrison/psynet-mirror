# Agent instructions

Read and follow `psynet/resources/experiment_scripts/AGENTS.md`.

## Environment setup notes

- If `python -m venv .venv` fails with `ensurepip` missing, install `python3.12-venv`.
- If `uv` is unavailable, install it in the venv with `python -m pip install uv`.
- If `uv pip install -e '.[dev,slack]'` fails building `psycopg2`, install
  `libpq-dev` and `python3.12-dev` (missing `pg_config` or `Python.h`).
