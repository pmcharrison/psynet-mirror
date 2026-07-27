import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from psynet.command_line import simulate
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory", "simulated_data_directory")
def test_simulate():
    runner = CliRunner()
    result = runner.invoke(simulate, [], catch_exceptions=False)
    print(result.output)
    assert result.exit_code == 0

    assert Path("data/simulated_data").exists()
    assert Path("data/simulated_data/database.zip").exists()
    assert Path("data/simulated_data/participant_identifiers.csv").exists()
    assert Path("data/simulated_data/manifest.json").exists()


@pytest.fixture
def simulated_data_directory():
    path = Path("data/simulated_data")
    shutil.rmtree(path, ignore_errors=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
