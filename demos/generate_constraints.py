#!/usr/bin/env python3

# Run me as follows: python3 demos/generate_constraints.py
# Warning: the chosen constraints will depend on the version of Dallinger that you currently have installed.
# In general, you want to make sure you have installed the version of Dallinger stated in PsyNet's setup.py.

import os
import pathlib
import subprocess

from yaspin import yaspin


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
    with yaspin(
        text=f"Generating constraints for {dir} demo...", color="green"
    ) as spinner:
        subprocess.run(
            "dallinger generate-constraints",
            shell=True,
            cwd=dir,
            capture_output=True,
        )
        spinner.ok("✔")
