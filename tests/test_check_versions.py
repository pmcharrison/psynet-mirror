import os
import tempfile

import pytest
from mock import patch

from psynet.utils import working_directory
from psynet.version import check_versions


# PsyNet tests
def test_skip_version_check_key_error():
    with pytest.raises(KeyError, match="'SKIP_VERSION_CHECK'"):
        del os.environ["SKIP_VERSION_CHECK"]

    os.environ["SKIP_VERSION_CHECK"] = "1"
    check_versions()
    del os.environ["SKIP_VERSION_CHECK"]


@patch("psynet.__version__", "10.0.0")
def test_check_versions_psynet_editable_version_tag_with_egg():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if versions specified and installed differ
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v9.9.9#egg=psynet"
                )
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The PsyNet versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: 10.0.0\n"
                    "Version specified in requirements.txt: 9.9.9",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
def test_check_versions_psynet_editable_version_tag_without_egg():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if versions specified and installed differ
            with open("requirements.txt", "w") as file:
                file.write("psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@v9.9.9")
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The PsyNet versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: 10.0.0\n"
                    "Version specified in requirements.txt: 9.9.9",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.get_pip_freeze_requirement")
def test_check_versions_psynet_editable_commit_hash(mock_get_pip_freeze_requirement):
    mock_get_pip_freeze_requirement.return_value = "-e git+ssh://git@gitlab.com/PsyNetDev/PsyNet@COMMIT_HASH_FROM_PIP_FREEEZE#egg=psynet"

    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if commit hashes specified and installed differ
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@COMMIT_HASH_FROM_REQUIREMENTS#egg=psynet\n"
                )
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The PsyNet versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: COMMIT_HASH_FROM_PIP_FREEEZE\n"
                    "Version specified in requirements.txt: COMMIT_HASH_FROM_REQUIREMENTS",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.get_pip_freeze_requirement")
def test_check_versions_psynet_pip_install_requirement(mock_get_pip_freeze_requirement):
    mock_get_pip_freeze_requirement.return_value = "psynet==10.0.0"

    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if versions specified (psynet==X.Y.Z) and installed differ
            with open("requirements.txt", "w") as file:
                file.write("psynet==9.9.9")
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The PsyNet versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: 10.0.0\n"
                    "Version specified in requirements.txt: 9.9.9",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.get_pip_freeze_requirement")
def test_check_versions_psynet_pip_install_commit_hash(mock_get_pip_freeze_requirement):
    mock_get_pip_freeze_requirement.return_value = "psynet==10.0.0"

    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if commit hash specified and version installed differ
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@a4d0d6153150deaae1b456f7dd5c081c5ef04b1d#egg=psynet\n"
                )
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The PsyNet versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: 10.0.0\n"
                    "Version specified in requirements.txt: a4d0d6153150deaae1b456f7dd5c081c5ef04b1d",
                ):
                    check_versions()


# Dallinger tests
@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.dallinger_version", "9.0.0")
def test_check_versions_dallinger_editable_requirement():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if dallinger version specified and installed differ
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.0.0#egg=psynet\n"
                    "dallinger==8.8.8"
                )
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The Dallinger versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: 9.0.0\n"
                    "Version specified in requirements.txt: 8.8.8",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.dallinger_version", "9.0.0")
def test_check_versions_dallinger_unspecified_requirement():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Do NOT raise an error if dallinger requirement is just specified with its package name
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.0.0#egg=psynet\n"
                    "dallinger"
                )
                file.flush()

                try:
                    check_versions()
                except AssertionError:
                    assert (
                        False
                    ), "The Dallinger versions installed on your local computer and specified in requirements.txt do not match."

            # Do NOT raise an error if dallinger requirement is not specified
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.0.0#egg=psynet"
                )
                file.flush()

                try:
                    check_versions()
                except AssertionError:
                    assert (
                        False
                    ), "The Dallinger versions installed on your local computer and specified in requirements.txt do not match."


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.get_pip_freeze_requirement")
def test_check_versions_dallinger_editable_commit_hash_with_egg(
    mock_get_pip_freeze_requirement,
):
    mock_get_pip_freeze_requirement.return_value = "-e git+https://github.com/Dallinger/Dallinger@COMMIT_HASH_FROM_PIP_FREEEZE#egg=dallinger"

    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if commit hashes specified and installed differ
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.0.0#egg=psynet\n"
                    "dallinger@git+https://github.com/Dallinger/Dallinger@COMMIT_HASH_FROM_REQUIREMENTS#egg=dallinger"
                )
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The Dallinger versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: COMMIT_HASH_FROM_PIP_FREEEZE\n"
                    "Version specified in requirements.txt: COMMIT_HASH_FROM_REQUIREMENTS",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.get_pip_freeze_requirement")
def test_check_versions_dallinger_editable_commit_hash_without_egg(
    mock_get_pip_freeze_requirement,
):
    mock_get_pip_freeze_requirement.return_value = (
        "-e git+https://github.com/Dallinger/Dallinger@COMMIT_HASH_FROM_PIP_FREEEZE"
    )

    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Raise an error if commit hashes specified and installed differ
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.0.0\n"
                    "dallinger@git+https://github.com/Dallinger/Dallinger@COMMIT_HASH_FROM_REQUIREMENTS"
                )
                file.flush()

                with pytest.raises(
                    AssertionError,
                    match="The Dallinger versions installed on your local computer and specified in requirements.txt do not match.\n\n"
                    "Version installed locally: COMMIT_HASH_FROM_PIP_FREEEZE\n"
                    "Version specified in requirements.txt: COMMIT_HASH_FROM_REQUIREMENTS",
                ):
                    check_versions()


@patch("psynet.__version__", "10.0.0")
@patch("psynet.version.dallinger_version", "9.0.0")
def test_check_dallinger_versions_pip_install():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Do NOT raise an error if dallinger version specified and installed are the same
            with open("requirements.txt", "w") as file:
                file.write(
                    "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.0.0#egg=psynet\n"
                    "dallinger==9.0.0"
                )
                file.flush()

                try:
                    check_versions()
                except AssertionError:
                    assert (
                        False
                    ), "The Dallinger versions installed on your local computer and specified in requirements.txt do not match."
