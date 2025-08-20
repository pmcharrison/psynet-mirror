from glob import glob
from pathlib import Path

import pytest
from click.testing import CliRunner

from psynet.command_line import simulate
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_simulate():
    runner = CliRunner()
    result = runner.invoke(simulate, [], catch_exceptions=False)
    print(result.output)
    assert result.exit_code == 0

    print("Contents of data/simulated_data:")
    for path in glob("data/simulated_data/**", recursive=True):
        print(path)

    assert Path("data/simulated_data").exists()
    assert Path("data/simulated_data/regular/data/AnimalTrial.csv").exists()
