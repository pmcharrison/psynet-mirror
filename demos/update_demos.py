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

import os
import pathlib
import subprocess

from joblib import Parallel, delayed

import psynet.command_line
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
        generate_constraints(dir)


def generate_constraints(dir):
    subprocess.run(
        "dallinger generate-constraints",
        shell=True,
        cwd=dir,
        capture_output=True,
    )


def update_scripts(dir):
    with working_directory(dir):
        psynet.command_line.update_scripts_()


if skip_constraints:
    n_jobs = 1
else:
    n_jobs = 16

Parallel(verbose=10, n_jobs=n_jobs)(
    delayed(update_demo)(_dir) for _dir in find_demo_dirs()
)
