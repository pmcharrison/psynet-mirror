#!/usr/bin/env python3
import os
import re
import subprocess
from pathlib import Path

from pytest_common import build_pytest_common_args


def list_lines(command):
    output = subprocess.check_output(command, text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def install_ci_dependencies(psynet_workspace):
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--no-cache",
            "--system",
            "--no-deps",
            "-e",
            psynet_workspace,
        ],
        check=True,
    )


def run_psynet_pytest(target, timeout_seconds, junit_xml=None):
    command = ["pytest"]
    if junit_xml is not None:
        command.append(f"--junitxml={junit_xml}")
    command.append(target)
    command.extend(build_pytest_common_args(timeout_seconds=timeout_seconds))
    return subprocess.run(command).returncode


def maybe_run_translation(ci_commit_ref_name):
    print("Checking if translation is needed...")
    print(f"CI_COMMIT_REF_NAME = {ci_commit_ref_name}")
    if re.match(r"^release-", ci_commit_ref_name):
        print("Release branch detected - will require all translations to be present.")
        return

    print(
        "Not a release branch - will use the null translator to populate any missing "
        "translations."
    )
    subprocess.run(["psynet", "translate", "--translator", "null"], check=True)


def main():
    ci_node_total = int(os.environ.get("CI_NODE_TOTAL", "1"))
    ci_node_index = int(os.environ.get("CI_NODE_INDEX", "1"))
    timeout_seconds = int(os.environ.get("TIMEOUT_SECONDS", "300"))
    ci_commit_ref_name = os.environ.get("CI_COMMIT_REF_NAME", "")
    psynet_workspace = os.environ.get("PSYNET_WORKSPACE", "/root/workspaces/PsyNet")

    print(f"Running tests on node {ci_node_index} of {ci_node_total}")

    print("Installing CI dependencies...")
    install_ci_dependencies(psynet_workspace)
    maybe_run_translation(ci_commit_ref_name)

    exit_code = 0

    experiment_dirs = list_lines(
        [
            "psynet",
            "list-experiment-dirs",
            "--for-ci-tests",
            "--ci-node-total",
            str(ci_node_total),
            "--ci-node-index",
            str(ci_node_index),
        ]
    )
    for experiment_dir in experiment_dirs:
        print(f"Testing experiment {experiment_dir}")
        return_code = run_psynet_pytest(
            target=f"{experiment_dir}/test.py",
            timeout_seconds=timeout_seconds,
            junit_xml=f"/public/{Path(experiment_dir).name}_junit.xml",
        )
        if return_code != 0:
            exit_code = 1

    isolated_tests = list_lines(
        [
            "psynet",
            "list-isolated-tests",
            "--ci-node-total",
            str(ci_node_total),
            "--ci-node-index",
            str(ci_node_index),
        ]
    )
    for isolated_test in isolated_tests:
        print(f"Testing isolated test {isolated_test}")
        return_code = run_psynet_pytest(
            target=isolated_test,
            timeout_seconds=timeout_seconds,
        )
        if return_code != 0:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
