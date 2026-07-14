"""Update PsyNet's bundled demo and test experiment files.

This module powers the source-checkout-only `psynet dev experiments update` command
group. Paths are resolved relative to the current working directory, so
contributors must run the commands from the PsyNet repository root.
"""

import fileinput
import os
import re
import shutil
import subprocess
from hashlib import md5
from pathlib import Path

from joblib import Parallel, delayed

from psynet.experiment_scaffold import prune_experiment_scaffold
from psynet.utils import (
    current_git_branch,
    get_psynet_root,
    list_experiment_dirs,
    working_directory,
)
from psynet.version import psynet_version, recommended_dallinger_major_minor


def update_command(n_jobs=8, skip_constraints_=None) -> int:
    """Update bundled demo and test experiment files from the source checkout."""
    assert_running_from_source_checkout_root()
    skip_constraints = (
        bool(os.getenv("SKIP_CONSTRAINTS"))
        if skip_constraints_ is None
        else skip_constraints_
    )

    # Constraint regeneration can pull a lower patch release unless we pin the latest
    # available Dallinger patch for PsyNet's recommended major/minor version.
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
        delayed(update_experiment)(
            _dir, skip_constraints, latest_dallinger_patch_version
        )
        for _dir in list_experiment_dirs()
    )
    return 0


def assert_running_from_source_checkout_root() -> None:
    """Fail fast when not running from the PsyNet source checkout root."""
    if Path.cwd().resolve() != get_psynet_root().resolve():
        raise ValueError(
            "This command must be run from the PsyNet source checkout root directory."
        )


def get_latest_dallinger_patch_version(major_minor_version):
    """Get the latest patch version for a given major.minor version of Dallinger."""
    try:
        # Use pip index to get available versions
        result = subprocess.run(
            ["pip", "index", "versions", "dallinger"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse the output to find versions matching the major.minor pattern
        lines = result.stdout.split("\n")
        versions = []

        for line in lines:
            if "Available versions:" in line:
                # Extract version numbers from this line
                version_part = line.split("Available versions:")[1].strip()
                versions = [v.strip() for v in version_part.split(",")]
                break

        # Filter versions that start with the major.minor version
        matching_versions = [
            v for v in versions if v.startswith(f"{major_minor_version}.")
        ]

        if matching_versions:
            # Sort versions and return the latest patch release
            matching_versions.sort(key=lambda x: tuple(map(int, x.split(".")[2:])))
            return matching_versions[-1]

        # Fallback to the major.minor version with .0
        return f"{major_minor_version}.0"

    except Exception:
        # Fallback to the major.minor version with .0 if we can't fetch versions
        return f"{major_minor_version}.0"


def use_master_psynet_reference():
    """Use the master branch for demos that should track unreleased alpha code."""
    return (
        current_git_branch() == "master"
        or re.search(r"a[0-9]+$", psynet_version) is not None
    )


def update_experiment(dir, skip_constraints, latest_dallinger_patch_version):
    """Refresh one experiment and restore the essential-files repository layout."""
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
    prune_scaffold(dir)


def generate_constraints(dir):
    """Regenerate constraints for one demo directory."""
    subprocess.run(
        "psynet generate-constraints",
        shell=True,
        cwd=dir,
        capture_output=True,
    )


def pre_update_constraints(dir):
    """Temporarily pin PsyNet before regenerating one demo's constraints."""
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
    """Normalize regenerated constraints and restore the experiment requirements."""
    with working_directory(dir):
        # Determine the correct psynet requirement for constraints.txt
        if use_master_psynet_reference():
            psynet_constraint = (
                "psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@master"
            )
        else:
            psynet_constraint = f"psynet=={psynet_version}"

        with fileinput.FileInput("constraints.txt", inplace=True) as file:
            for line in file:
                updated_line = line

                # Replace any psynet git reference with the version number
                if "psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@" in updated_line:
                    updated_line = updated_line.replace(
                        updated_line.strip(), psynet_constraint
                    )

                # Replace any existing psynet version with the current version
                # Matches e.g. "psynet==13.0.0rc2"
                updated_line = re.sub(
                    r"^psynet==[^\s]+",
                    psynet_constraint,
                    updated_line,
                )

                # Ensure Dallinger is pinned to the latest patch version
                # Matches e.g. "dallinger==11.5.2"
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
    """Rewrite the demo's PsyNet requirement to the current branch version."""
    with working_directory(dir):
        # Determine the correct psynet requirement based on branch
        if use_master_psynet_reference():
            # Keep the git reference that was set in pre_update_constraints.
            return  # Don't override the git reference

        with open("requirements.txt", "r") as orig_file:
            with open("updated_requirements.txt", "w") as updated_file:
                version = r"([0-9]+)\.([0-9]+)\.([0-9]+(?:rc[0-9]+|a[0-9]+)?)"
                for line in orig_file:
                    # Handle psynet==X.Y.Z format
                    match = re.search(
                        r"^psynet(\s?)==(\s?)" + version + "$",
                        line,
                    )
                    if match is not None:
                        updated_file.write(re.sub(version, f"{psynet_version}", line))
                    # Handle psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet format
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
    """Refresh the generated constraints header after requirements changes."""
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
    """Refresh scaffold-managed files for one demo directory."""
    with working_directory(dir):
        from psynet.command_line import update_scripts_

        update_scripts_(skip_files={"README.md"})


def prune_scaffold(dir):
    """Remove scaffold-managed files from a demo after refreshing it."""
    with working_directory(dir):
        prune_experiment_scaffold(preserve_files={"README.md"}, force=True)


def update_image_tag(file):
    """Rewrite scaffold image tags to match the current branch or release version."""
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
