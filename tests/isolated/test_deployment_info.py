import subprocess
import tempfile
from pathlib import Path

import pytest

from psynet import deployment_info
from psynet.utils import working_directory


def test_deployment_info():
    with tempfile.TemporaryDirectory() as tempdir:
        with working_directory(tempdir):
            with pytest.raises(FileNotFoundError):
                deployment_info.read("x")

            deployment_info.reset()

            deployment_info.write(x=3)
            assert deployment_info.read("x") == 3

            deployment_info.reset()

            with pytest.raises(KeyError):
                deployment_info.read("x")


def _git(*args):
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _initialize_deployment_info():
    deployment_info.init(
        redeploying_from_archive=False,
        mode="debug",
        is_local_deployment=True,
        is_ssh_deployment=False,
        server=None,
        app=None,
    )


def test_deployment_info_records_git_provenance(tmp_path):
    with working_directory(tmp_path):
        _git("init", "--quiet")
        _git("config", "user.email", "test@example.com")
        _git("config", "user.name", "Test User")
        tracked_file = Path("experiment.py")
        tracked_file.write_text("content")
        _git("add", "experiment.py")
        _git("commit", "--quiet", "-m", "Initial commit")

        _initialize_deployment_info()

        assert deployment_info.read("git_commit_sha") == _git("rev-parse", "HEAD")
        assert deployment_info.read("git_dirty") is False

        tracked_file.write_text("changed")
        _initialize_deployment_info()

        assert deployment_info.read("git_dirty") is True


def test_deployment_info_handles_missing_git_repository(tmp_path):
    with working_directory(tmp_path):
        _initialize_deployment_info()

        assert deployment_info.read("git_commit_sha") is None
        assert deployment_info.read("git_dirty") is None
