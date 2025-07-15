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
from importlib import resources

from joblib import Parallel, delayed

import psynet.command_line
from psynet import __version__
from psynet.utils import list_experiment_dirs, working_directory

skip_constraints = bool(os.getenv("SKIP_CONSTRAINTS"))


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
        return psynet.command_line.pre_update_constraints_(dir)


def post_update_constraints(dir, commit_hash_master):
    with working_directory(dir):
        psynet.command_line.post_update_constraints_(commit_hash_master)


def update_psynet_requirement(dir):
    with working_directory(dir):
        psynet.command_line.update_psynet_requirement_()


def post_update_psynet_requirement(dir):
    with working_directory(dir):
        psynet.command_line.post_update_psynet_requirement_()


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


def current_git_branch():
    return (
        subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.STDOUT
        )
        .strip()
        .decode("utf-8")
    )


def update_image_tag(file):
    branch_tag = "psynet:master"
    version_tag = r"psynet:v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(rc\d+|a\d+)*"

    for line in file:
        if current_git_branch() == "master":
            print(re.sub(version_tag, "psynet:master", line), end="")
        else:
            if re.search(version_tag, line):
                print(re.sub(version_tag, f"psynet:v{__version__}", line), end="")
            elif re.search(branch_tag, line):
                print(re.sub(branch_tag, f"psynet:v{__version__}", line), end="")
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
