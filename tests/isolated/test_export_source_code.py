from pathlib import Path
from zipfile import ZipFile

import pytest
import requests

from psynet.pytest_psynet import path_to_demo


@pytest.mark.usefixtures("launched_experiment")
@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_download_source_missing_credentials(launched_experiment):
    response = requests.get("http://localhost:5000/download_source")

    assert response.status_code == 401
    assert response.reason == "UNAUTHORIZED"
    assert response.json()["message"] == "Invalid credentials"


@pytest.mark.usefixtures("launched_experiment")
@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_download_source_wrong_credentials(launched_experiment):
    response = requests.get(
        "http://localhost:5000/download_source",
        auth=("wrong", "credentials"),
    )

    assert response.status_code == 401
    assert response.reason == "UNAUTHORIZED"
    assert response.json()["message"] == "Invalid credentials"


@pytest.mark.usefixtures("launched_experiment")
@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_download_source_success(launched_experiment):
    response = requests.get(
        "http://localhost:5000/download_source",
        auth=("test_admin", "test_password"),
    )

    assert response.status_code == 200

    zip_filename = "source_code.zip"
    cleanup(zip_filename)

    with open(zip_filename, "wb") as f:
        f.write(response.content)

    with ZipFile(zip_filename, "r") as zip_file:
        assert "experiment/" in zip_file.namelist()

    cleanup(zip_filename)


def cleanup(zip_filename):
    Path(zip_filename).unlink(missing_ok=True)
