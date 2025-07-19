# test_artifact_1.py runs artifact tests that use the hello_world experiment.
# test_artifact_2.py run tests that use the artifact_storage experiment.
# This separation is necessary because only one experiment can be imported per test process.

import os
import tempfile
import time
import zipfile

import pandas as pd
import pytest
import requests

from psynet.artifact import LocalArtifactStorage
from psynet.pytest_psynet import path_to_demo_experiment


def test_list_subfolders(artifact_storage, tmp_path):
    storage = artifact_storage

    # Create two folders with different times
    first_file = tmp_path / "first.txt"
    first_file.write_text("first text")
    storage.upload(str(first_file), "subfolder_test/first_folder/first.txt")

    time.sleep(0.1)

    second_file = tmp_path / "second.txt"
    second_file.write_text("second text")
    storage.upload(str(second_file), "subfolder_test/second_folder/second.txt")

    subfolders = storage.list_subfolders("subfolder_test")

    # Folders are sorted with the most recent first
    assert subfolders == ["second_folder", "first_folder"]


def test_upload_and_download(artifact_storage, tmp_path):
    storage = artifact_storage
    # Create a file to upload
    src_file = tmp_path / "src.txt"
    src_file.write_text("hello")
    # Upload to storage
    storage.upload(str(src_file), "uploaded.txt")
    # Download to new location
    dest_file = tmp_path / "dest.txt"
    storage.download("uploaded.txt", str(dest_file))
    assert dest_file.read_text() == "hello"


def test_move_file(artifact_storage, tmp_path):
    storage = artifact_storage
    # Create and upload a file
    src_file = tmp_path / "src.txt"
    src_file.write_text("move me")
    storage.upload(str(src_file), "to_move.txt")
    # Move within storage
    storage.move_file("to_move.txt", "moved/to_move.txt")
    if isinstance(storage, LocalArtifactStorage):
        moved_path = os.path.join(storage.root, "moved", "to_move.txt")
        assert os.path.exists(moved_path)
        with open(moved_path) as f:
            assert f.read() == "move me"
    else:
        # Download from new location and check contents
        dest_file = tmp_path / "moved.txt"
        storage.download("moved/to_move.txt", str(dest_file))
        assert dest_file.read_text() == "move me"


def test_move_missing_file_raises(artifact_storage):
    storage = artifact_storage
    with pytest.raises(FileNotFoundError):
        storage.move_file("does_not_exist.txt", "target.txt")


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("hello_world")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestAPI:
    def test_exp(self, launched_experiment):
        deployment_id = launched_experiment.deployment_id
        base_url = "http://localhost:5000"

        self.check_commenting(base_url, deployment_id)
        self.check_export(base_url, deployment_id)

    def check_commenting(self, base_url, deployment_id):
        comment_text = "This is a test comment."

        # Write the comment
        response = requests.post(
            f"{base_url}/dashboard/comment/set/{deployment_id}",
            data={"txt": comment_text},
        )
        assert response.status_code == 200

        # Download the comment
        response = requests.get(
            f"{base_url}/dashboard/artifact/{deployment_id}/comment.txt"
        )
        assert response.status_code == 200
        assert response.text == comment_text

    def check_export(self, base_url, deployment_id):
        # Request a data export (in psynet mode, without assets)
        response = requests.get(
            f"{base_url}/dashboard/export/download",
            params={"type": "psynet", "assets": "none"},
        )
        assert response.status_code == 200
        # Inspect it and check that it contains the ExperimentConfig.csv file
        with tempfile.TemporaryDirectory() as tempdir:
            zip_path = os.path.join(tempdir, "export.zip")
            with open(zip_path, "wb") as f:
                f.write(response.content)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tempdir)
                found = False
                for root, dirs, files in os.walk(tempdir):
                    if "ExperimentConfig.csv" in files:
                        found = True
                        csv_path = os.path.join(root, "ExperimentConfig.csv")
                        df = pd.read_csv(csv_path)
                        assert len(df) >= 1
                        break
                assert found, "ExperimentConfig.csv not found in export."
