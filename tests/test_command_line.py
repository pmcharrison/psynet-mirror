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


@pytest.mark.parametrize("experiment_directory", ["../demos/static"], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
class TestDebug:
    # Note:
    # We do not test non-legacy debug here because of an issue whereby you
    # can't use hot-refresh mode when running PsyNet demos unless the
    # PsyNet installation folder is renamed to something other than 'psynet'.
    # It's not a big deal but maybe we fix this sometime.
    @patch("psynet.command_line.prepare")
    @patch("dallinger.command_line.debug")
    def test_debug(self, dallinger_debug, prepare):
        from psynet.command_line import debug

        CliRunner().invoke(debug, ["--legacy"], catch_exceptions=False)

        # We can no longer run this test for prepare, because it is now called in a subprocess,
        # so isn't caught by the mock.
        # prepare.assert_called_once_with(force=False)

        dallinger_debug.assert_called_once_with(
            verbose=False,
            bot=False,
            proxy=None,
            no_browsers=False,
            exp_config={"threads": "1"},
        )

    @patch("psynet.command_line.prepare")
    @patch("dallinger.command_line.debug")
    def test_debug_all_non_default(self, dallinger_debug, prepare):
        from psynet.command_line import debug

        CliRunner().invoke(
            debug,
            [
                "--legacy",
                "--verbose",
                "--bot",
                "--proxy=5001",
                "--no-browsers",
                "--force-prepare",
            ],
            catch_exceptions=False,
        )

        # We can no longer run this test for prepare, because it is now called in a subprocess,
        # so isn't caught by the mock.
        # prepare.assert_called_once_with(force=True)

        dallinger_debug.assert_called_once_with(
            verbose=True,
            bot=True,
            proxy="5001",
            no_browsers=True,
            exp_config={"threads": "1"},
        )


@pytest.mark.parametrize("experiment_directory", ["../demos/static"], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
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
        with patch("dallinger.command_line.deploy") as mock_dallinger_deploy:
            yield mock_dallinger_deploy

    def test_deploy(self, deploy, prepare, dallinger_deploy):
        CliRunner().invoke(deploy, [], catch_exceptions=False)

        # We can no longer run this test for prepare, because it is now called in a subprocess,
        # so isn't caught by the mock.
        # prepare.assert_called_once_with(force=False)

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
            catch_exceptions=False,
        )

        # We can no longer run this test for prepare, because it is now called in a subprocess,
        # so isn't caught by the mock.
        # prepare.assert_called_once_with(force=True)

        dallinger_deploy.assert_called_once_with(
            verbose=True, app="some_app_name", archive="/path/to/some_archive"
        )


@pytest.mark.parametrize("experiment_directory", ["../demos/static"], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
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
        with patch("dallinger.command_line.sandbox") as mock_dallinger_sandbox:
            yield mock_dallinger_sandbox

    def test_sandbox(self, sandbox, prepare, dallinger_sandbox):
        CliRunner().invoke(sandbox, [], catch_exceptions=False)

        # We can no longer run this test for prepare, because it is now called in a subprocess,
        # so isn't caught by the mock.
        # prepare.assert_called_once_with(force=False)

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
            catch_exceptions=False,
        )

        # We can no longer run this test for prepare, because it is now called in a subprocess,
        # so isn't caught by the mock.
        # prepare.assert_called_once_with(force=True)

        dallinger_sandbox.assert_called_once_with(
            verbose=True, app="some_app_name", archive="/path/to/some_archive"
        )


@pytest.mark.parametrize("experiment_directory", ["../demos/static"], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
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

    @pytest.fixture
    def pretty_format_seconds(self):
        with patch(
            "psynet.command_line.pretty_format_seconds"
        ) as mock_pretty_format_seconds:
            yield mock_pretty_format_seconds

    def test_estimate(
        self, estimate, prepare, import_local_experiment, pretty_format_seconds
    ):
        CliRunner().invoke(estimate, [], catch_exceptions=False)
        prepare.assert_not_called()
        import_local_experiment.assert_called_once()
        pretty_format_seconds.assert_called_once()


@pytest.mark.parametrize("experiment_directory", ["../demos/static"], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
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
        result = CliRunner().invoke(export, catch_exceptions=False)
        assert b"Usage: export [OPTIONS]" in result.stdout_bytes
        assert b"Error: Missing option '--app'." in result.stdout_bytes
        assert result.exit_code == 2
