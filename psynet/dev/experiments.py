"""Update PsyNet's canonical standalone-experiment templates.

This module powers the source-checkout-only `psynet dev experiments update` command
group. Bundled demos intentionally omit generated scaffold and dependency files.
"""

import fileinput
import re
from pathlib import Path

from psynet.utils import (
    current_git_branch,
    get_psynet_root,
)
from psynet.version import psynet_version


def update_command() -> int:
    """Update canonical experiment templates from the source checkout."""
    assert_running_from_source_checkout_root()

    # Update PsyNet Docker image version.
    for path in [
        "psynet/resources/experiment_scripts/Dockerfile",
        "psynet/resources/experiment_scripts/docker/generate-constraints",
    ]:
        with fileinput.FileInput(path, inplace=True) as file:
            update_image_tag(file)

    return 0


def assert_running_from_source_checkout_root() -> None:
    """Fail fast when not running from the PsyNet source checkout root."""
    if Path.cwd().resolve() != get_psynet_root().resolve():
        raise ValueError(
            "This command must be run from the PsyNet source checkout root directory."
        )


def use_master_psynet_reference():
    """Use the master image tag for unreleased alpha code."""
    return (
        current_git_branch() == "master"
        or re.search(r"a[0-9]+$", psynet_version) is not None
    )


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
