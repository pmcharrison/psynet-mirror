#!/usr/bin/env python3

# Run me as follows: python3 demos/update_gitignore.py

import os
import pathlib


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
    path = os.path.join(dir, ".gitignore")
    with open(path, "w") as f:
        lines = [
            "env  # standard place to put a virtual environment",
            "deploy  # automatically generated deployment resources, e.g. database templates",
            "develop  # used by hot-refresh debugger",
            "static/local_storage  # used when debugging experiments with local storage",
        ]
        f.write("\n".join(lines))
