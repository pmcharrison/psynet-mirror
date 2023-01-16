#!/usr/bin/env python3

# Run me as follows: python3 demos/add_tests.py

import os
import pathlib
import shutil

reference_folder = pathlib.Path(__file__).parent.parent.joinpath(
    "tests/template_experiment_tests"
)
files = ["test.py", "pytest.ini"]


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
        [dir for dir, sub_dirs, files in os.walk(root_dir) if "experiment.py" in files]
    )


for dir in find_demo_dirs():
    for file in files:
        shutil.copyfile(
            reference_folder.joinpath(file), pathlib.Path(dir).joinpath(file)
        )
