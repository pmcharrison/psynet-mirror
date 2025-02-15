import os
import tempfile

import pytest

from psynet.command_line import verify_psynet_requirement
from psynet.utils import working_directory


def test_verify_psynet_requirement_missing_version():
    try:
        del os.environ["SKIP_CHECK_PSYNET_VERSION_REQUIREMENT"]
    except KeyError:
        pass

    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            with open("requirements.txt", "w") as file:
                file.write("psynet\n")
                file.flush()

                with pytest.raises(
                    AssertionError, match="Incorrect specification for PsyNet"
                ):
                    verify_psynet_requirement()


def test_verify_psynet_requirement_extension():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            os.environ["SKIP_CHECK_PSYNET_VERSION_REQUIREMENT"] = "1"
            verify_psynet_requirement()
            del os.environ["SKIP_CHECK_PSYNET_VERSION_REQUIREMENT"]

            for extension in ["", ".git"]:
                with open("requirements.txt", "w") as file:
                    file.write(
                        f"psynet@git+https://gitlab.com/PsyNetDev/PsyNet{extension}\n"
                    )
                    file.flush()

                    with pytest.raises(
                        AssertionError, match="Incorrect specification for PsyNet"
                    ):
                        verify_psynet_requirement()


def test_verify_psynet_requirement_commit_hash():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            for extension in ["", ".git"]:
                for egg in ["", "#egg=psynet"]:
                    with open("requirements.txt", "w") as file:
                        file.write(
                            f"psynet@git+https://gitlab.com/PsyNetDev/PsyNet{extension}@45f317688af59350f9a6f3052fd73076318f2775{egg}\n"
                        )
                        file.flush()

                        verify_psynet_requirement()


def test_verify_psynet_requirement_short_commit_hash():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            for extension in ["", ".git"]:
                for egg in ["", "#egg=psynet"]:
                    with open("requirements.txt", "w") as file:
                        file.write(
                            f"psynet@git+https://gitlab.com/PsyNetDev/PsyNet{extension}@45f31768{egg}\n"
                        )
                        file.flush()

                        verify_psynet_requirement()


def test_verify_psynet_requirement_version_tag():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            for extension in ["", ".git"]:
                for egg in ["", "#egg=psynet"]:
                    for space in ["", " "]:
                        for rc in ["", "rc0"]:
                            with open("requirements.txt", "w") as file:
                                file.write(
                                    f"psynet{space}@{space}git+https://gitlab.com/PsyNetDev/PsyNet{extension}@v10.1.0{rc}{egg}\n"
                                )
                                file.flush()

                                verify_psynet_requirement()


def test_verify_psynet_requirement_name_based():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            with open("requirements.txt", "w") as file:
                file.write("psynet==10.1.0\n")
                file.flush()

                verify_psynet_requirement()


def test_verify_psynet_requirement_name_based_with_spaces():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            with open("requirements.txt", "w") as file:
                file.write("psynet == 10.1.0\n")
                file.flush()

                verify_psynet_requirement()
