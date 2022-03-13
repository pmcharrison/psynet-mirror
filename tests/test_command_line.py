import subprocess

import pytest
from click.testing import CliRunner
from mock import patch


class TestCommandLine(object):
    @pytest.fixture
    def export(self):
        from psynet.command_line import export

        return export

    def test_psynet_no_args(self):
        output = subprocess.check_output(["psynet"])
        assert b"Usage: psynet [OPTIONS] COMMAND [ARGS]" in output

    def test_psynet_help(self):
        output = subprocess.check_output(["psynet", "--help"])
        assert b"Options:" in output
        assert b"Commands:" in output


@pytest.mark.usefixtures("demo_static")
class TestDebug:
    @pytest.fixture
    def debug(self):
        from psynet.command_line import debug

        return debug

    @pytest.fixture
    def prepare(self):
        with patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_debug(self):
        with patch("psynet.command_line.dallinger_debug") as mock_dallinger_debug:
            yield mock_dallinger_debug

    def test_debug(self, debug, prepare, dallinger_debug):
        CliRunner().invoke(debug, [])
        prepare.assert_called_once_with(force=False)
        dallinger_debug.assert_called_once_with(
            verbose=False,
            bot=False,
            proxy=None,
            no_browsers=False,
            exp_config={"threads": "1"},
        )

    def test_debug_all_non_default(self, debug, prepare, dallinger_debug):
        CliRunner().invoke(
            debug,
            ["--verbose", "--bot", "--proxy=5001", "--no-browsers", "--force-prepare"],
        )
        prepare.assert_called_once_with(force=True)
        dallinger_debug.assert_called_once_with(
            verbose=True,
            bot=True,
            proxy="5001",
            no_browsers=True,
            exp_config={"threads": "1"},
        )


@pytest.mark.usefixtures("demo_static")
class TestDeploy:
    @pytest.fixture
    def deploy(self):
        from psynet.command_line import deploy

        return deploy

    @pytest.fixture
    def prepare(self):
        with patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_deploy(self):
        with patch("psynet.command_line.dallinger_deploy") as mock_dallinger_deploy:
            yield mock_dallinger_deploy

    def test_deploy(self, deploy, prepare, dallinger_deploy):
        CliRunner().invoke(deploy, [])
        prepare.assert_called_once_with(force=False)
        dallinger_deploy.assert_called_once_with(verbose=False, app=None, archive=None)

    def test_deploy_all_non_default(self, deploy, prepare, dallinger_deploy):
        CliRunner().invoke(
            deploy,
            [
                "--verbose",
                "--app=some_app_name",
                "--archive=/path/to/some_archive",
                "--force-prepare",
            ],
        )
        prepare.assert_called_once_with(force=True)
        dallinger_deploy.assert_called_once_with(
            verbose=True, app="some_app_name", archive="/path/to/some_archive"
        )


@pytest.mark.usefixtures("demo_static")
class TestSandbox:
    @pytest.fixture
    def sandbox(self):
        from psynet.command_line import sandbox

        return sandbox

    @pytest.fixture
    def prepare(self):
        with patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_sandbox(self):
        with patch("psynet.command_line.dallinger_sandbox") as mock_dallinger_sandbox:
            yield mock_dallinger_sandbox

    def test_sandbox(self, sandbox, prepare, dallinger_sandbox):
        CliRunner().invoke(sandbox, [])
        prepare.assert_called_once_with(force=False)
        dallinger_sandbox.assert_called_once_with(verbose=False, app=None, archive=None)

    def test_sandbox_all_non_default(self, sandbox, prepare, dallinger_sandbox):
        CliRunner().invoke(
            sandbox,
            [
                "--verbose",
                "--app=some_app_name",
                "--archive=/path/to/some_archive",
                "--force-prepare",
            ],
        )
        prepare.assert_called_once_with(force=True)
        dallinger_sandbox.assert_called_once_with(
            verbose=True, app="some_app_name", archive="/path/to/some_archive"
        )


@pytest.mark.usefixtures("demo_static")
class TestEstimate:
    @pytest.fixture
    def estimate(self):
        from psynet.command_line import estimate

        return estimate

    @pytest.fixture
    def prepare(self):
        with patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def import_local_experiment(self):
        with patch(
            "psynet.command_line.import_local_experiment"
        ) as mock_import_local_experiment:
            yield mock_import_local_experiment

    def test_estimate(self, estimate, import_local_experiment, prepare):
        CliRunner().invoke(estimate, [])
        prepare.assert_not_called()
        import_local_experiment.assert_called_once()


@pytest.mark.usefixtures("demo_static")
class TestExport:
    @pytest.fixture
    def export(self):
        from psynet.command_line import export

        return export

    @pytest.fixture
    def prepare(self):
        with patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_data_export(self):
        with patch(
            "psynet.command_line.dallinger_data.export"
        ) as mock_dallinger_data_export:
            yield mock_dallinger_data_export

    @pytest.fixture
    def import_local_experiment(self):
        with patch(
            "psynet.command_line.import_local_experiment"
        ) as mock_import_local_experiment:
            yield mock_import_local_experiment

    @pytest.fixture
    def create_export_dirs(self):
        with patch("psynet.command_line.create_export_dirs") as mock_create_export_dirs:
            yield mock_create_export_dirs

    @pytest.fixture
    def move_snapshot_file(self):
        with patch("psynet.command_line.move_snapshot_file") as mock_move_snapshot_file:
            yield mock_move_snapshot_file

    @pytest.fixture
    def export_data(self):
        with patch("psynet.command_line.export_data") as mock_export_data:
            yield mock_export_data

    def test_export_missing_app_param(self, export):
        result = CliRunner().invoke(export)
        assert b"Usage: export [OPTIONS]" in result.stdout_bytes
        assert b"Error: Missing option '--app'." in result.stdout_bytes
        assert result.exit_code == 2
