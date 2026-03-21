#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path


def build_docker_run_command(image_tag, workspace_path, workdir, command):
    postgres_ip = os.environ.get("POSTGRES_IP")
    redis_ip = os.environ.get("REDIS_IP")
    if not postgres_ip or not redis_ip:
        raise RuntimeError("POSTGRES_IP and REDIS_IP must be set.")

    cwd = Path.cwd()

    return [
        "docker",
        "run",
        f"--add-host=postgres:{postgres_ip}",
        f"--add-host=redis:{redis_ip}",
        "-e",
        "HEADLESS=TRUE",
        "-e",
        "REDIS_URL",
        "-e",
        "DATABASE_URL",
        "-e",
        "POSTGRES_DB",
        "-e",
        "POSTGRES_USER",
        "-e",
        "POSTGRES_PASSWORD",
        "-e",
        "AWS_ACCESS_KEY_ID",
        "-e",
        "AWS_DEFAULT_REGION",
        "-e",
        "AWS_SECRET_ACCESS_KEY",
        "-e",
        "CI",
        "-e",
        "CI_NODE_TOTAL",
        "-e",
        "CI_NODE_INDEX",
        "-e",
        "CI_COMMIT_REF_NAME",
        "-e",
        f"PSYNET_WORKSPACE={workspace_path}",
        "-v",
        f"{cwd}:{workspace_path}",
        "-v",
        f"{cwd / 'public'}:/public",
        "-w",
        workdir,
        image_tag,
        *command,
    ]


def main():
    if len(sys.argv) < 5:
        print(
            "Usage: run_ci_docker_command.py <image_tag> <workspace_path> "
            "<workdir> <command> [args...]",
            file=sys.stderr,
        )
        return 1

    image_tag = sys.argv[1]
    workspace_path = sys.argv[2]
    workdir = sys.argv[3]
    command = sys.argv[4:]

    subprocess.run(
        build_docker_run_command(image_tag, workspace_path, workdir, command), check=True
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
