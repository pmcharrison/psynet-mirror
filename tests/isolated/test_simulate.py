import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from click.testing import CliRunner

from psynet.audit.cli import init_audit
from psynet.command_line import audit_simulate
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_audit_simulate(audit_directory):
    runner = CliRunner()
    result = runner.invoke(audit_simulate, [], catch_exceptions=False)
    print(result.output)
    assert result.exit_code == 0

    archive_path = Path("audit/artifacts/simulated_data.zip")
    assert archive_path.is_file()
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert "database/participant.csv" in names
    assert "participant_identifiers.csv" in names
    assert "manifest.json" in names
    assert "source_code.zip" not in names
    assert not Path("data/simulated_data").exists()
    assert not Path("exports").exists()


@pytest.fixture
def audit_directory():
    path = Path("audit")
    shutil.rmtree(path, ignore_errors=True)
    init_audit(path)
    yield path
    shutil.rmtree(path, ignore_errors=True)
