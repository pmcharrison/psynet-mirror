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
from importlib import resources

from joblib import Parallel, delayed

import psynet.command_line
from psynet import __version__
from psynet.utils import list_demo_dirs, working_directory

skip_constraints = bool(os.getenv("SKIP_CONSTRAINTS"))


def update_demo(dir):
    update_scripts(dir)
    if not skip_constraints:
        generate_constraints(dir)
        post_update_constraints(dir)
        update_psynet_requirement(dir)


def generate_constraints(dir):
    subprocess.run(
        "psynet generate-constraints",
        shell=True,
        cwd=dir,
        capture_output=True,
    )


def post_update_constraints(dir):
    with working_directory(dir):
        psynet.command_line.post_update_constraints_()


def update_psynet_requirement(dir):
    with working_directory(dir):
        psynet.command_line.update_psynet_requirement_()


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


# Update PsyNet Docker image version
for path in [
    "psynet/resources/experiment_scripts/Dockerfile",
    "psynet/resources/experiment_scripts/docker/generate-constraints",
]:
    with fileinput.FileInput(path, inplace=True) as file:
        version_tag = "psynet:v(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)"
        for line in file:
            print(re.sub(version_tag, f"psynet:v{__version__}", line), end="")

# Update demos
n_jobs = 8
Parallel(verbose=10, n_jobs=n_jobs)(
    delayed(update_demo)(_dir) for _dir in list_demo_dirs()
)
