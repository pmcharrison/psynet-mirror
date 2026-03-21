#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pytest_common import build_pytest_common_args
from run_ci_docker_command import build_docker_run_command

PSYNET_URL_PREFIX = "git+https://gitlab.com/PsyNetDev/PsyNet@"
PSYNET_NORMALIZED_PREFIX = "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@"
DALLINGER_CONSTRAINTS_GENERATOR_URL = (
    "https://raw.githubusercontent.com/Dallinger/Dallinger/master/dallinger/constraints.py"
)


def normalize_dependency_line(line):
    return re.sub(r"\s+", "", line.lstrip())


def extract_psynet_ref(normalized_line):
    if not normalized_line.startswith(PSYNET_NORMALIZED_PREFIX):
        return None

    ref = normalized_line[len(PSYNET_NORMALIZED_PREFIX) :]
    ref = ref.split("#", 1)[0]
    ref = ref.split(";", 1)[0]
    return ref


def rewrite_psynet_master_pin(line, ci_commit_sha):
    return re.sub(
        r"git\+https://gitlab\.com/PsyNetDev/PsyNet@master",
        f"{PSYNET_URL_PREFIX}{ci_commit_sha}",
        line,
        count=1,
    )


def regenerate_constraints(base_image_tag, build_experiment_dir):
    requirements_file = build_experiment_dir / "requirements.txt"
    if not requirements_file.exists():
        return

    print(f"Regenerating constraints for {build_experiment_dir}...")
    regenerate_command = (
        f'curl -s "{DALLINGER_CONSTRAINTS_GENERATOR_URL}" | uv run - generate'
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{build_experiment_dir}:/experiment",
            "-w",
            "/experiment",
            base_image_tag,
            "sh",
            "-lc",
            regenerate_command,
        ],
        check=True,
    )


def discover_experiments(base_image_tag):
    discover_script = (
        "from pathlib import Path\n"
        "from psynet.utils import get_psynet_root, list_docker_build_experiment_dirs\n"
        "root = get_psynet_root()\n"
        "for directory in list_docker_build_experiment_dirs():\n"
        "    print(Path(directory).relative_to(root))\n"
    )
    output = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{Path.cwd()}:/workspace",
            "-w",
            "/workspace",
            "-e",
            "PYTHONPATH=/workspace",
            base_image_tag,
            "python",
            "-c",
            discover_script,
        ],
        text=True,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def rewrite_psynet_dependency_file(dependency_file, ci_commit_sha):
    if not dependency_file.exists():
        return False

    found_psynet_dependency = False
    rewritten_lines = []

    for line in dependency_file.read_text().splitlines(keepends=True):
        normalized = normalize_dependency_line(line)

        if not normalized or normalized.startswith("#"):
            rewritten_lines.append(line)
            continue

        ref = extract_psynet_ref(normalized)
        if ref is not None:
            found_psynet_dependency = True
            if ref != "master":
                raise ValueError(
                    f"Invalid PsyNet pin in {dependency_file}: {line.rstrip()}\n"
                    "Custom Docker experiments must reference PsyNet@master."
                )

            rewritten_lines.append(rewrite_psynet_master_pin(line, ci_commit_sha))
            continue

        if normalized.startswith("psynet@git+"):
            raise ValueError(
                f"Invalid PsyNet source in {dependency_file}: {line.rstrip()}\n"
                "Custom Docker experiments must use gitlab.com/PsyNetDev/PsyNet."
            )

        if normalized.startswith("psynet"):
            raise ValueError(
                f"Invalid PsyNet dependency in {dependency_file}: {line.rstrip()}\n"
                "Custom Docker experiments must use PsyNet@master."
            )

        rewritten_lines.append(line)

    dependency_file.write_text("".join(rewritten_lines))
    return found_psynet_dependency


def prepare_build_context(
    experiment_dir, experiment_name, build_context_root, ci_commit_sha, base_image_tag
):
    build_experiment_dir = Path(
        tempfile.mkdtemp(prefix=f"{experiment_name}.", dir=build_context_root)
    )
    shutil.copytree(experiment_dir, build_experiment_dir, dirs_exist_ok=True)
    regenerate_constraints(base_image_tag, build_experiment_dir)

    found_psynet_dependency = False
    for dependency_filename in ("requirements.txt", "constraints.txt"):
        found_psynet_dependency = rewrite_psynet_dependency_file(
            build_experiment_dir / dependency_filename, ci_commit_sha
        ) or found_psynet_dependency

    if not found_psynet_dependency:
        raise ValueError(
            f"No PsyNet dependency found for {experiment_dir}.\n"
            "Custom Docker experiments must pin PsyNet@master in requirements.txt "
            "or constraints.txt."
        )

    return build_experiment_dir


def tail_file(file_path, line_count=200):
    if not file_path.exists():
        return []
    return file_path.read_text(errors="replace").splitlines()[-line_count:]


def run_diagnostic(image_tag, experiment_dir, experiment_name, timeout_seconds):
    diagnostic_log = Path("public") / f"{experiment_name}_diagnostic.log"
    diagnostic_cmd = [
        "pytest",
        f"--junitxml=/public/{experiment_name}_junit.xml",
        "test.py",
        *build_pytest_common_args(
            timeout_seconds=timeout_seconds,
            log_cli=True,
            quiet=False,
        ),
        "-vv",
        "-s",
    ]

    print(f"Collecting fallback diagnostics in {diagnostic_log}")
    with diagnostic_log.open("w", encoding="utf-8") as diagnostic_output:
        result = subprocess.run(
            build_docker_run_command(
                image_tag, "/workspace", f"/workspace/{experiment_dir}", diagnostic_cmd
            ),
            stdout=diagnostic_output,
            stderr=subprocess.STDOUT,
        )
    if result.returncode == 0:
        print("Diagnostic rerun unexpectedly succeeded.")
    else:
        print(f"Diagnostic rerun failed with exit code {result.returncode}")

    if diagnostic_log.stat().st_size > 0:
        print(f"Last 200 lines from {diagnostic_log}:")
        for line in tail_file(diagnostic_log, 200):
            print(line)
    else:
        print(f"Diagnostic log is also empty: {diagnostic_log}")


def run_experiment_tests(image_tag, experiment_dir, experiment_name, timeout_seconds):
    log_file = Path("public") / f"{experiment_name}.log"
    pytest_cmd = [
        "pytest",
        f"--junitxml=/public/{experiment_name}_junit.xml",
        "test.py",
        *build_pytest_common_args(
            timeout_seconds=timeout_seconds,
        ),
    ]

    print(f"Running tests for {experiment_dir}")
    print(f"Writing test output to {log_file}")

    with log_file.open("w", encoding="utf-8") as test_output:
        result = subprocess.run(
            build_docker_run_command(
                image_tag, "/workspace", f"/workspace/{experiment_dir}", pytest_cmd
            ),
            stdout=test_output,
            stderr=subprocess.STDOUT,
        )
    if result.returncode == 0:
        return 0

    print(f"Tests failed for {experiment_dir} with exit code {result.returncode}")
    if log_file.exists() and log_file.stat().st_size > 0:
        print(f"Last 200 lines from {log_file}:")
        for line in tail_file(log_file, 200):
            print(line)
    elif log_file.exists():
        print(f"Log file exists but is empty: {log_file}")
        run_diagnostic(image_tag, experiment_dir, experiment_name, timeout_seconds)
    else:
        print(f"No log file was created for {experiment_dir}.")
    return 1


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: run_docker_experiment_tests.py <base_image_tag> [timeout_seconds]",
            file=sys.stderr,
        )
        return 1

    base_image_tag = sys.argv[1]
    timeout_seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    ci_commit_sha = os.environ.get("CI_COMMIT_SHA")
    if not ci_commit_sha:
        print("CI_COMMIT_SHA is required for docker experiment builds.", file=sys.stderr)
        return 1

    Path("public").mkdir(parents=True, exist_ok=True)
    experiment_dirs = discover_experiments(base_image_tag)
    if not experiment_dirs:
        print("No docker-build experiments configured.")
        return 0

    exit_code = 0
    with tempfile.TemporaryDirectory() as build_context_root:
        for experiment_dir in experiment_dirs:
            experiment_name = Path(experiment_dir).name
            image_tag = f"custom-{experiment_name}"
            build_experiment_dir = prepare_build_context(
                Path(experiment_dir),
                experiment_name,
                build_context_root,
                ci_commit_sha,
                base_image_tag,
            )

            print(f"Building Docker image for {experiment_dir} with PsyNet@{ci_commit_sha}")
            subprocess.run(
                ["docker", "build", "--tag", image_tag, str(build_experiment_dir)],
                check=True,
            )

            exit_code = (
                run_experiment_tests(
                    image_tag, experiment_dir, experiment_name, timeout_seconds
                )
                or exit_code
            )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
