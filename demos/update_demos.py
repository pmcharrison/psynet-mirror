# Run me as follows: python3 demos/update_demos.py
#
# Warning: the chosen constraints will depend on the version of Dallinger that you currently have installed.
# In general, you want to make sure you have installed the version of Dallinger stated in PsyNet's setup.py.
#
# Warning: this command currently takes several minutes to complete because generating constraints.txt files is slow.
# We plan to remove these constraints.txt files in due course from PsyNet, but currently they are required for
# Dallinger back-compatibility.
# In the meantime, if you want to skip generating constraints and only update other demo files,
# run the following instead: SKIP_CONSTRAINTS=1 python3 demos/update_demos.py

import fileinput
import os
import pathlib
import re
import shutil
import subprocess
from importlib import resources

from joblib import Parallel, delayed

import psynet.command_line
from psynet import __version__
from psynet.utils import working_directory

skip_constraints = bool(os.getenv("SKIP_CONSTRAINTS"))


def find_demo_dirs():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """

    root_dir = pathlib.Path(__file__).parent.resolve()
    return sorted(
        [
            dir
            for dir, sub_dirs, files in os.walk(root_dir)
            if "experiment.py" in files and not dir.endswith("/develop")
        ]
    )


def update_demo(dir):
    update_scripts(dir)
    if not skip_constraints:
        update_psynet_requirement(dir)
        generate_constraints(dir)
        post_update_constraints(dir)


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
with fileinput.FileInput(
    "psynet/resources/experiment_scripts/Dockerfile", inplace=True
) as file:
    version = "psynet:v(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)"
    for line in file:
        print(re.sub(version, f"psynet:v{__version__}", line), end="")

# Update demos
n_jobs = 8
Parallel(verbose=10, n_jobs=n_jobs)(
    delayed(update_demo)(_dir) for _dir in find_demo_dirs()
)
