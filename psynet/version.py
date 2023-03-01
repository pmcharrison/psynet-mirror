import os
import re

# Bump versions by changing these two lines. setup.py will read them automatically.
dallinger_minimum_version = "9.4.3"
psynet_version = "10.0.0rc3"

dallinger_minimum_version_parts = dallinger_minimum_version.split(".")
dallinger_maximum_major_version = int(dallinger_minimum_version_parts[0]) + 1
dallinger_maximum_version = f"{dallinger_maximum_major_version}.0.0"
dallinger_version_requirement = (
    f"dallinger>={dallinger_minimum_version}, <{dallinger_maximum_version}"
)


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
