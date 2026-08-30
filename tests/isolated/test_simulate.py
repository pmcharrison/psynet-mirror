import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from psynet.audit.cli import init_audit
from psynet.command_line import simulate
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory", "audit_directory")
def test_simulate():
    runner = CliRunner()
    result = runner.invoke(simulate, [], catch_exceptions=False)
    print(result.output)
    assert result.exit_code == 0

    export = Path("audit/simulate/analysis/simulated_export")
    assert export.exists()
    assert (export / "regular/data/AnimalTrial.csv").exists()
    assert not Path("data/simulated_data").exists()


@pytest.fixture
def audit_directory():
    path = Path("audit")
    init_audit(path)
    yield path
    shutil.rmtree(path)
