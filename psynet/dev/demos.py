"""Update PsyNet's bundled demo and test experiment files.

This module powers the source-checkout-only `psynet dev demos update` command
group. Paths are resolved relative to the current working directory, so
contributors must run the commands from the PsyNet repository root.
"""

import argparse
import fileinput
import os
import re
import shutil
import subprocess
from hashlib import md5
from importlib import resources
from pathlib import Path

from joblib import Parallel, delayed

from psynet.utils import current_git_branch, list_experiment_dirs, working_directory
from psynet.version import psynet_version, recommended_dallinger_major_minor

SOURCE_CHECKOUT_PATHS = (
    Path("psynet/resources/experiment_scripts/Dockerfile"),
    Path("psynet/resources/experiment_scripts/docker/generate-constraints"),
    Path("demos"),
)


def main() -> int:
    """Run the argparse-based entry point used by the compatibility wrapper."""
    args = parse_args()
    return update_command(
        n_jobs=args.legacy_jobs if args.legacy_jobs is not None else args.jobs,
        skip_constraints_=args.skip_constraints,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for direct script execution."""
    parser = argparse.ArgumentParser(
        description=(
            "Update PsyNet's bundled demo and test experiment files. "
            "Normally run via: psynet dev demos update."
        )
    )
    parser.add_argument(
        "--jobs",
        default=8,
        type=int,
        help="Number of parallel jobs to use when updating demos.",
    )
    parser.add_argument(
        "--skip-constraints",
        action="store_true",
        help="Update demo files without regenerating constraints.txt files.",
    )
    parser.add_argument(
        "legacy_jobs",
        nargs="?",
        type=int,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def update_command(n_jobs=8, skip_constraints_=None) -> int:
    """Update bundled demo files from the current PsyNet source checkout."""
    assert_demos_available()
    skip_constraints = (
        bool(os.getenv("SKIP_CONSTRAINTS"))
        if skip_constraints_ is None
        else skip_constraints_
    )

    # Fetch the latest Dallinger patch version once, outside of parallel execution.
    latest_dallinger_patch_version = get_latest_dallinger_patch_version(
        recommended_dallinger_major_minor
    )

    # Update PsyNet Docker image version.
    for path in [
        "psynet/resources/experiment_scripts/Dockerfile",
        "psynet/resources/experiment_scripts/docker/generate-constraints",
    ]:
        with fileinput.FileInput(path, inplace=True) as file:
            update_image_tag(file)

    # Use importable package functions for Joblib workers. Dynamically loaded
    # modules cannot be imported by Loky child processes during unpickling.
    Parallel(verbose=10, n_jobs=n_jobs)(
        delayed(update_demo)(_dir, skip_constraints, latest_dallinger_patch_version)
        for _dir in list_experiment_dirs()
    )
    return 0


def assert_demos_available() -> None:
    """Fail fast when not running from a PsyNet source checkout."""
    missing_paths = [path for path in SOURCE_CHECKOUT_PATHS if not path.exists()]
    if missing_paths:
        raise ValueError(
            "Run from a PsyNet source checkout: "
            + ", ".join(str(path) for path in missing_paths)
            + " must exist in the current directory."
        )


def get_latest_dallinger_patch_version(major_minor_version):
    """Get the latest patch version for a given major.minor version of Dallinger."""
    try:
        result = subprocess.run(
            ["pip", "index", "versions", "dallinger"],
            capture_output=True,
            text=True,
            check=True,
        )

        lines = result.stdout.split("\n")
        versions = []

        for line in lines:
            if "Available versions:" in line:
                version_part = line.split("Available versions:")[1].strip()
                versions = [v.strip() for v in version_part.split(",")]
                break

        matching_versions = [
            v for v in versions if v.startswith(f"{major_minor_version}.")
        ]

        if matching_versions:
            matching_versions.sort(key=lambda x: tuple(map(int, x.split(".")[2:])))
            return matching_versions[-1]

        return f"{major_minor_version}.0"

    except (subprocess.CalledProcessError, Exception):
        return f"{major_minor_version}.0"


def use_master_psynet_reference():
    """Use the master branch for demos that should track unreleased alpha code."""
    return (
        current_git_branch() == "master"
        or re.search(r"a[0-9]+$", psynet_version) is not None
    )


def update_demo(dir, skip_constraints, latest_dallinger_patch_version):
    update_scripts(dir)
    if not skip_constraints:
        commit_hash_master = pre_update_constraints(dir)
        generate_constraints(dir)
        post_update_constraints(
            dir,
            commit_hash_master,
            latest_dallinger_patch_version,
        )
        update_psynet_requirement(dir)
        post_update_psynet_requirement(dir)


def generate_constraints(dir):
    subprocess.run(
        "psynet generate-constraints",
        shell=True,
        cwd=dir,
        capture_output=True,
    )


def pre_update_constraints(dir):
    with working_directory(dir):
        commit_hash = (
            subprocess.check_output(
                ["git", "log", "-n 1", "master", "--pretty=format:%H"], cwd=dir
            )
            .decode("utf-8")
            .strip()
        )
        with fileinput.FileInput("requirements.txt", inplace=True) as file:
            psynet_requirement = (
                r"psynet==([0-9]+)\.([0-9]+)\.([0-9]+(?:rc[0-9]+|a[0-9]+)?)"
            )
            replacement_requirement = f"psynet@git+https://gitlab.com/PsyNetDev/PsyNet@{commit_hash}#egg=psynet"
            if use_master_psynet_reference():
                replacement_requirement = (
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet"
                )
            for line in file:
                print(
                    re.sub(
                        psynet_requirement,
                        replacement_requirement,
                        line,
                    ),
                    end="",
                )
        return commit_hash


def post_update_constraints(dir, commit_hash_master, latest_dallinger_patch_version):
    with working_directory(dir):
        if use_master_psynet_reference():
            psynet_constraint = (
                "psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@master"
            )
        else:
            psynet_constraint = f"psynet=={psynet_version}"

        with fileinput.FileInput("constraints.txt", inplace=True) as file:
            for line in file:
                updated_line = line

                if "psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@" in updated_line:
                    updated_line = updated_line.replace(
                        updated_line.strip(), psynet_constraint
                    )

                updated_line = re.sub(
                    r"^psynet==[^\s]+",
                    psynet_constraint,
                    updated_line,
                )

                updated_line = re.sub(
                    r"^dallinger==[^\s]+",
                    f"dallinger=={latest_dallinger_patch_version}",
                    updated_line,
                )

                print(updated_line, end="")

        with fileinput.FileInput("requirements.txt", inplace=True) as file:
            psynet_requirement = f"psynet@git+https://gitlab.com/PsyNetDev/PsyNet@{commit_hash_master}#egg=psynet"
            for line in file:
                print(
                    line.replace(psynet_requirement, f"psynet=={psynet_version}"),
                    end="",
                )


def update_psynet_requirement(dir):
    with working_directory(dir):
        if use_master_psynet_reference():
            return

        with open("requirements.txt", "r") as orig_file:
            with open("updated_requirements.txt", "w") as updated_file:
                version = r"([0-9]+)\.([0-9]+)\.([0-9]+(?:rc[0-9]+|a[0-9]+)?)"
                for line in orig_file:
                    match = re.search(
                        r"^psynet(\s?)==(\s?)" + version + "$",
                        line,
                    )
                    if match is not None:
                        updated_file.write(re.sub(version, f"{psynet_version}", line))
                    elif (
                        "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet"
                        in line
                    ):
                        updated_file.write(f"psynet=={psynet_version}\n")
                    else:
                        updated_file.write(line)
                updated_file.close()
            orig_file.close()
        shutil.move("updated_requirements.txt", "requirements.txt")


def post_update_psynet_requirement(dir):
    with working_directory(dir):
        constraints_path = Path("constraints.txt")
        md5sum = md5(Path("requirements.txt").read_bytes()).hexdigest()
        python_version = Path(".python-version").read_text().strip()

        old_pattern = (
            r"# Compiled from a requirements\.txt file with md5sum [0-9a-f]{32}.*"
        )
        new_line = (
            f"# Compiled from a requirements.txt file with md5sum {md5sum} "
            f"and a .python-version file requesting Python {python_version}"
        )

        content = constraints_path.read_text()
        content = re.sub(old_pattern, new_line, content)
        constraints_path.write_text(content)


def update_scripts(dir):
    with working_directory(dir):
        from psynet.command_line import update_scripts_

        update_scripts_()

        with resources.as_file(
            resources.files("psynet") / "resources/experiment_scripts/config.txt"
        ) as path:
            shutil.copyfile(
                path,
                "config.txt",
            )


def update_image_tag(file):
    branch_tag = "psynet:master"
    version_tag = r"psynet:v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(rc\d+|a\d+)*"

    for line in file:
        if use_master_psynet_reference():
            print(re.sub(version_tag, "psynet:master", line), end="")
        else:
            if re.search(version_tag, line):
                print(re.sub(version_tag, f"psynet:v{psynet_version}", line), end="")
            elif re.search(branch_tag, line):
                print(re.sub(branch_tag, f"psynet:v{psynet_version}", line), end="")
            else:
                print(line, end="")


if __name__ == "__main__":
    raise SystemExit(main())
