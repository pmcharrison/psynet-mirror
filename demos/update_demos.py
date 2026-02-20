# Run me as follows: python3 demos/update_demos.py
#
# Warning: the chosen constraints will depend on the version of Dallinger that you currently have installed.
# In general, you want to make sure you have installed the version of Dallinger stated in PsyNet's `psynet/version.py`.
#
# Warning: this command currently takes several minutes to complete because generating constraints.txt files is slow.
# We plan to remove these constraints.txt files in due course from PsyNet, but currently they are required for
# Dallinger back-compatibility.
# In the meantime, if you want to skip generating constraints and only update other demo files,
# run the following instead: SKIP_CONSTRAINTS=1 python3 demos/update_demos.py

import fileinput
import os
import re
import shutil
import subprocess
import sys
from hashlib import md5
from importlib import resources
from pathlib import Path

from joblib import Parallel, delayed

import psynet.command_line
from psynet.utils import current_git_branch, list_experiment_dirs, working_directory
from psynet.version import dallinger_recommended_version, psynet_version


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
            # Sort versions and return the latest
            matching_versions.sort(key=lambda x: tuple(map(int, x.split(".")[2:])))
            return matching_versions[-1]
        else:
            # Fallback to the major.minor version with .0
            return f"{major_minor_version}.0"

    except (subprocess.CalledProcessError, Exception):
        # Fallback to the major.minor version with .0 if we can't fetch
        return f"{major_minor_version}.0"


skip_constraints = bool(os.getenv("SKIP_CONSTRAINTS"))

# Fetch the latest Dallinger patch version once, outside of parallel execution
latest_dallinger_patch_version = get_latest_dallinger_patch_version(
    dallinger_recommended_version
)


def update_demo(dir):
    update_scripts(dir)
    if not skip_constraints:
        commit_hash_master = pre_update_constraints(dir)
        generate_constraints(dir)
        post_update_constraints(dir, commit_hash_master)
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
            if current_git_branch() == "master":
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


def post_update_constraints(dir, commit_hash_master):
    with working_directory(dir):
        current_branch = current_git_branch()

        # Determine the correct psynet requirement for constraints.txt based on branch
        if current_branch == "master":
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
                    f"psynet=={psynet_version}",
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
    with working_directory(dir):
        current_branch = current_git_branch()

        # Determine the correct psynet requirement based on branch
        if current_branch == "master":
            # On master branch, keep the git reference that was set in pre_update_constraints
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
        psynet.command_line.update_scripts_()

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
        if current_git_branch() == "master":
            print(re.sub(version_tag, "psynet:master", line), end="")
        else:
            if re.search(version_tag, line):
                print(re.sub(version_tag, f"psynet:v{psynet_version}", line), end="")
            elif re.search(branch_tag, line):
                print(re.sub(branch_tag, f"psynet:v{psynet_version}", line), end="")
            else:
                print(line, end="")


# Update PsyNet Docker image version
for path in [
    "psynet/resources/experiment_scripts/Dockerfile",
    "psynet/resources/experiment_scripts/docker/generate-constraints",
]:
    with fileinput.FileInput(path, inplace=True) as file:
        update_image_tag(file)

# Update demos
n_jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 8
Parallel(verbose=10, n_jobs=n_jobs)(
    delayed(update_demo)(_dir) for _dir in list_experiment_dirs()
)
