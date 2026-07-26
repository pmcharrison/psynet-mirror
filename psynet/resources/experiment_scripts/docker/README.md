# README

This directory contains scripts for running PsyNet commands through Docker.
We are currently considering removing this route to focus on the standard
virtual environment route. For the latest guidance,
please visit the [PsyNet website](https://psynet.dev).

These deprecated scripts call `docker build` directly. Docker does not read the
experiment's `deploy.toml`, and PsyNet no longer generates `.dockerignore`
because deployment backends must share one file plan. The generated
`docker/build` script therefore refuses to run when `deploy.toml` is present.
Use the standard PsyNet or Dallinger commands so the reviewed plan controls the
Docker context. Older scripts and direct builds without a policy can send local
files such as `.env` and `.venv` to the Docker daemon.
