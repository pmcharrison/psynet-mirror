import os
import re
import subprocess

from dallinger.version import __version__ as dallinger_version
from yaspin import yaspin

# Bump versions by changing these two lines. setup.py will read them automatically.
dallinger_minimum_version = "9.10.0"
psynet_version = "10.4.0"

dallinger_minimum_version_parts = dallinger_minimum_version.split(".")
dallinger_maximum_major_version = int(dallinger_minimum_version_parts[0]) + 1
dallinger_maximum_version = f"{dallinger_maximum_major_version}.0.0"
dallinger_version_requirement = (
    f"dallinger>={dallinger_minimum_version}, <{dallinger_maximum_version}"
)


def check_versions():
    "Check whether the PsyNet and Dallinger versions installed locally match the ones specified in the requirements.txt file."
    if os.environ.get("SKIP_VERSION_CHECK"):
        print(
            "SKIP_VERSION_CHECK is set so we will skip checking PsyNet versions specified vs. installed."
        )
        return

    with yaspin(
        text="Checking whether PsyNet and Dallinger versions specified and installed are the same...",
        color="green",
    ) as spinner:
        with open("requirements.txt", "r") as file:
            versions = get_all_version_infos(file.read())

            for package_name, version_infos in versions.items():
                consistent = version_infos["consistent"]

                if consistent:
                    spinner.ok("✔")
                else:
                    spinner.color = "red"
                    spinner.fail("✗")

                    assert consistent, (
                        f"The {package_name} versions installed on your local computer and specified in requirements.txt do not match.\n"
                        f'\nVersion installed locally: {version_infos["installed"]}'
                        f'\nVersion specified in requirements.txt: {version_infos["specified"]}'
                        "\n\nYou can skip this check by writing `export SKIP_VERSION_CHECK=1` (without quotes) in your terminal."
                    )


def get_all_version_infos(file_content):
    versions = {}
    for package_name in ["Dallinger", "PsyNet"]:
        versions[package_name] = {
            "specified": None,
            "installed": None,
            "consistent": True,
        }
        specified = None
        installed = None

        requirements = [
            line for line in file_content.splitlines() if package_name.lower() in line
        ]

        if len(requirements) == 0:
            continue

        requirement = requirements[0]

        match = re.search(
            f"/{package_name}@(.*)#egg={package_name}", requirement, re.IGNORECASE
        )
        if match is None:
            match = re.search(f"/{package_name}@(.*)", requirement, re.IGNORECASE)

        # We either assume PsyNet is specified in the correct requirement syntax
        # or as a standard requirement (e.g. 'psynet==10.0.0')
        specified = (
            match.group(1) if match is not None else re.split("==", requirement)[-1]
        )

        # In case just specified as the package name
        if specified == package_name.lower():
            continue

        if specified_using_version(specified):
            if specified.startswith("v"):
                specified = specified[1:]
            # Get installed version via the Dallinger/PsyNet API
            installed = installed_version_for(package_name)
        else:
            # Get installed version from `pip freeze`
            installed = commit_hash_or_version_from_pip_freeze(package_name)

        consistent = specified is None or specified == installed

        versions[package_name] = {
            "specified": specified,
            "installed": installed,
            "consistent": consistent,
        }

    return versions


def specified_using_version(specified):
    return (
        specified.startswith("v")
        or re.search(r"^\d+\.\d+\.\d+$", specified) is not None
    )


def installed_version_for(package_name):
    import psynet

    if package_name == "Dallinger":
        return dallinger_version
    if package_name == "PsyNet":
        return psynet.__version__
    raise ValueError(f"Unsupported package '{package_name}'")


def get_pip_freeze_requirement(name):
    pip_freeze_stdout = subprocess.run(
        ["pip freeze"],
        shell=True,
        capture_output=True,
    ).stdout

    return [
        line.decode()
        for line in pip_freeze_stdout.splitlines()
        if f"{name}" in line.decode()
    ][0]


def commit_hash_or_version_from_pip_freeze(package_name):
    line = get_pip_freeze_requirement(package_name)
    match = re.search(f"{package_name}@(.*)#egg={package_name}", line, re.IGNORECASE)
    if match is None:
        match = re.search(f"{package_name}@(.*)", line, re.IGNORECASE)
    if match is not None:
        return match.group(1)
    return line.split("==")[-1]


def parse_version(x):
    parts = x.split(".")
    assert len(parts) == 3, f"Invalid version specifier: {x}"

    major, minor, patch = parts

    # Strip anything that comes after a letter, so that e.g. 9.4.0a1 -> "9.4.0"
    patch = re.sub("[a-zA-Z].*", "", patch)

    return int(major), int(minor), int(patch)


def version_is_greater(x, y, strict: bool = True):
    """
    Returns True if version number x is (strictly) greater than version number y.
    """
    x_parsed = parse_version(x)
    y_parsed = parse_version(y)

    for x_i, y_i in zip(x_parsed, y_parsed):
        if x_i < y_i:
            return False
        elif x_i > y_i:
            return True
    if strict:
        return False
    else:
        return True


def check_dallinger_version():
    import dallinger

    current_dallinger_version = dallinger.version.__version__

    environment_variable = "SKIP_CHECK_DALLINGER_VERSION"
    if not os.environ.get(environment_variable, None):
        if not (
            version_is_greater(
                current_dallinger_version, dallinger_minimum_version, strict=False
            )
            and version_is_greater(
                dallinger_maximum_version, current_dallinger_version, strict=True
            )
        ):
            raise ValueError(
                f"The current installed version of Dallinger ({current_dallinger_version}) "
                f"is incompatible with PsyNet's requirements ({dallinger_version_requirement}). "
                "Please install an appropriate version of Dallinger, or (only if you know what you're doing!) "
                f"disable this check by setting the environment variable {environment_variable} to a non-empty string."
            )
