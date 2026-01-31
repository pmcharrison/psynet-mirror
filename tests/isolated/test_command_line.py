import hashlib
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from psynet.command_line import _check_constraints, _check_dockerfile_format
from psynet.pytest_psynet import path_to_test_experiment
from psynet.utils import working_directory


class TestCommandLine(object):
    @pytest.fixture
    def export(self):
        from psynet.command_line import export

        return export

    def test_psynet_no_args(self):
        result = subprocess.run(["psynet"], capture_output=True, text=True)
        assert "Usage: psynet [OPTIONS] COMMAND [ARGS]" in result.stderr

    def test_psynet_help(self):
        output = subprocess.check_output(["psynet", "--help"])
        assert b"Options:" in output
        assert b"Commands:" in output

    def test_install_autocomplete_help(self):
        """Test that the install autocomplete command shows help."""
        output = subprocess.check_output(
            ["psynet", "install", "autocomplete", "--help"]
        )
        assert b"Install shell tab completion" in output

    @patch("subprocess.run")
    @patch("os.path.exists")
    @patch("os.chmod")
    def test_install_autocomplete_success(self, mock_chmod, mock_exists, mock_run):
        """Test successful installation of autocomplete."""
        from psynet.command_line import install_autocomplete

        mock_exists.return_value = True
        mock_run.return_value.returncode = 0

        runner = CliRunner()
        result = runner.invoke(install_autocomplete)

        assert result.exit_code == 0
        # Check that the script was made executable and run
        mock_chmod.assert_called_once()
        mock_run.assert_called_once()

        # Verify the last call to exists was for the install script
        last_exists_call = mock_exists.call_args_list[-1]
        assert "install-completion.sh" in str(last_exists_call)

    @patch("os.path.exists")
    def test_install_autocomplete_script_not_found(self, mock_exists):
        """Test that install autocomplete fails when script is not found."""
        from psynet.command_line import install_autocomplete

        mock_exists.return_value = False

        runner = CliRunner()
        result = runner.invoke(install_autocomplete)

        assert result.exit_code != 0
        assert "Installation script not found" in result.output


# Disabled because our method of importing means that we can't patch
# the necessary Dallinger commands. I think this is fine, I don't
# think these tests add much value.
#
# @pytest.mark.parametrize("experiment_directory", [path_to_test_experiment("timeline")], indirect=True)
# @pytest.mark.usefixtures("in_experiment_directory")
# class TestDebug:
#     # Note:
#     # We do not test non-legacy debug here because of an issue whereby you
#     # can't use hot-refresh mode when running PsyNet demos unless the
#     # PsyNet installation folder is renamed to something other than 'psynet'.
#     # It's not a big deal but maybe we fix this sometime.
#     @patch("psynet.command_line.prepare")
#     @patch("dallinger.command_line.debug")
#     def test_debug(self, dallinger_debug, prepare):
#         from psynet.command_line import debug
#
#         CliRunner().invoke(debug, ["--legacy"], catch_exceptions=False)
#
#         # We can no longer run this test for prepare, because it is now called in a subprocess,
#         # so isn't caught by the mock.
#         # prepare.assert_called_once_with(force=False)
#
#         dallinger_debug.assert_called_once_with(
#             verbose=False,
#             bot=False,
#             proxy=None,
#             no_browsers=False,
#             exp_config={"threads": "1"},
#             archive=None,
#         )
#
#     @patch("psynet.command_line.prepare")
#     @patch("dallinger.command_line.debug")
#     def test_debug_all_non_default(self, dallinger_debug, prepare):
#         from psynet.command_line import debug
#
#         CliRunner().invoke(
#             debug,
#             [
#                 "--legacy",
#                 "--verbose",
#                 "--bot",
#                 "--proxy=5001",
#                 "--no-browsers",
#                 "--force-prepare",
#             ],
#             catch_exceptions=False,
#         )
#
#         # We can no longer run this test for prepare, because it is now called in a subprocess,
#         # so isn't caught by the mock.
#         # prepare.assert_called_once_with(force=True)
#
#         dallinger_debug.assert_called_once_with(
#             verbose=True,
#             bot=True,
#             proxy="5001",
#             no_browsers=True,
#             exp_config={"threads": "1"},
#         )
#
#
# @pytest.mark.parametrize("experiment_directory", [path_to_test_experiment("timeline")], indirect=True)
# @pytest.mark.usefixtures("in_experiment_directory")
# class TestDeploy:
#     @pytest.fixture
#     def deploy(self):
#         from psynet.command_line import deploy
#
#         return deploy
#
#     @pytest.fixture
#     def prepare(self):
#         with patch("psynet.command_line.prepare") as mock_prepare:
#             yield mock_prepare
#
#     @pytest.fixture
#     def dallinger_deploy(self):
#         with patch("dallinger.command_line.deploy") as mock_dallinger_deploy:
#             yield mock_dallinger_deploy
#
#     def test_deploy(self, deploy, prepare, dallinger_deploy):
#         CliRunner().invoke(deploy, [], catch_exceptions=False)
#
#         # We can no longer run this test for prepare, because it is now called in a subprocess,
#         # so isn't caught by the mock.
#         # prepare.assert_called_once_with(force=False)
#
#         dallinger_deploy.assert_called_once_with(verbose=False, app=None, archive=None)
#
#     def test_deploy_all_non_default(self, deploy, prepare, dallinger_deploy):
#         CliRunner().invoke(
#             deploy,
#             [
#                 "--verbose",
#                 "--app=some_app_name",
#                 "--archive=/path/to/some_archive",
#                 "--force-prepare",
#             ],
#             catch_exceptions=False,
#         )
#
#         # We can no longer run this test for prepare, because it is now called in a subprocess,
#         # so isn't caught by the mock.
#         # prepare.assert_called_once_with(force=True)
#
#         dallinger_deploy.assert_called_once_with(
#             verbose=True, app="some_app_name", archive="/path/to/some_archive"
#         )
#
#
# @pytest.mark.parametrize("experiment_directory", [path_to_test_experiment("timeline")], indirect=True)
# @pytest.mark.usefixtures("in_experiment_directory")
# class TestSandbox:
#     @pytest.fixture
#     def sandbox(self):
#         from psynet.command_line import sandbox
#
#         return sandbox
#
#     @pytest.fixture
#     def prepare(self):
#         with patch("psynet.command_line.prepare") as mock_prepare:
#             yield mock_prepare
#
#     @pytest.fixture
#     def dallinger_sandbox(self):
#         with patch("dallinger.command_line.sandbox") as mock_dallinger_sandbox:
#             yield mock_dallinger_sandbox
#
#     def test_sandbox(self, sandbox, prepare, dallinger_sandbox):
#         CliRunner().invoke(sandbox, [], catch_exceptions=False)
#
#         # We can no longer run this test for prepare, because it is now called in a subprocess,
#         # so isn't caught by the mock.
#         # prepare.assert_called_once_with(force=False)
#
#         dallinger_sandbox.assert_called_once_with(verbose=False, app=None, archive=None)
#
#     def test_sandbox_all_non_default(self, sandbox, prepare, dallinger_sandbox):
#         CliRunner().invoke(
#             sandbox,
#             [
#                 "--verbose",
#                 "--app=some_app_name",
#                 "--archive=/path/to/some_archive",
#                 "--force-prepare",
#             ],
#             catch_exceptions=False,
#         )
#
#         # We can no longer run this test for prepare, because it is now called in a subprocess,
#         # so isn't caught by the mock.
#         # prepare.assert_called_once_with(force=True)
#
#         dallinger_sandbox.assert_called_once_with(
#             verbose=True, app="some_app_name", archive="/path/to/some_archive"
#         )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
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
            "psynet.experiment.import_local_experiment"
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


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
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
            "psynet.experiment.import_local_experiment"
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

    def test_export_logs_success(self, tmp_path):
        """Test successful log file export."""
        from unittest.mock import Mock, patch

        from psynet.command_line import export_logs

        mock_executor = Mock()
        mock_sftp = Mock()
        mock_server_info = {"host": "test-host", "user": "test-user"}
        mock_spinner = Mock()

        with (
            patch(
                "dallinger.command_line.docker_ssh.CONFIGURED_HOSTS",
                {"test-server": mock_server_info},
            ),
            patch("dallinger.command_line.docker_ssh.get_sftp", return_value=mock_sftp),
            patch(
                "dallinger.command_line.docker_ssh.Executor", return_value=mock_executor
            ),
            patch("psynet.command_line.log") as mock_log,
            patch("psynet.command_line.yaspin") as mock_yaspin,
        ):

            mock_yaspin.return_value.__enter__.return_value = mock_spinner
            mock_executor.run.return_value.strip.return_value = "/home/testuser"

            # Test log file export
            export_logs("test-app", "test-server", str(tmp_path))

            # Verify the call was made
            assert mock_sftp.get.call_count == 1

            # Verify correct path
            mock_sftp.get.assert_called_with(
                "/home/testuser/dallinger/test-app/logs.jsonl",
                str(tmp_path / "logs.jsonl"),
            )

            # Verify log message
            mock_log.assert_called_with(f"Exporting logs to {tmp_path}/logs.jsonl")

            # Verify success spinner was shown (function ran to completion)
            assert mock_yaspin.call_count == 1
            mock_yaspin.assert_called_with(text="Logs exported.", color="green")
            assert mock_spinner.ok.call_count == 1

    def test_export_logs_error_handling(self, tmp_path):
        """Test error handling in log file export."""
        from unittest.mock import Mock, patch

        from psynet.command_line import export_logs

        mock_executor = Mock()
        mock_sftp = Mock()
        mock_server_info = {"host": "test-host", "user": "test-user"}

        # Test SFTP failure
        mock_sftp.get.side_effect = Exception("Permission denied")

        with (
            patch(
                "dallinger.command_line.docker_ssh.CONFIGURED_HOSTS",
                {"test-server": mock_server_info},
            ),
            patch("dallinger.command_line.docker_ssh.get_sftp", return_value=mock_sftp),
            patch(
                "dallinger.command_line.docker_ssh.Executor", return_value=mock_executor
            ),
            patch("psynet.command_line.log") as mock_log,
        ):

            mock_executor.run.return_value.strip.return_value = "/home/testuser"

            export_logs("test-app", "test-server", str(tmp_path))

            # Verify the error message includes the specific path
            mock_log.assert_called_with(
                "Warning: Failed to export logs from /home/testuser/dallinger/test-app/logs.jsonl: Permission denied"
            )


def test_check_constraints():
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            with pytest.raises(
                click.ClickException,
                match="Experiment directory is missing a requirements.txt file.",
            ):
                _check_constraints()

            with open("requirements.txt", "w") as requirements:
                requirements.write("psynet")
                requirements.flush()

                with pytest.raises(
                    click.ClickException,
                    match="Experiment directory is missing a constraints.txt file.",
                ):
                    _check_constraints()

                with open("constraints.txt", "w") as constraints:
                    with pytest.raises(
                        click.ClickException,
                        match="The constraints.txt file is not up-to-date with the requirements.txt file.",
                    ):
                        _check_constraints()

                    requirements_hash = hashlib.md5(
                        Path("requirements.txt").read_bytes()
                    ).hexdigest()
                    constraints.write(requirements_hash)
                    constraints.flush()

                    _check_constraints()


def test_check_dockerfile_format():
    """Test that _check_dockerfile_format detects outdated Dockerfiles."""
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Test 1: No Dockerfile - should not raise
            _check_dockerfile_format()
            
            # Test 2: Dockerfile with new format (python:3.13) - should not raise
            with open("Dockerfile", "w") as f:
                f.write("FROM python:3.13-bookworm\n")
                f.write("RUN pip install psynet\n")
            
            _check_dockerfile_format()
            
            # Test 3: Dockerfile with old format and PsyNet >= 13.1.0 - should raise
            with open("Dockerfile", "w") as f:
                f.write("FROM registry.gitlab.com/psynetdev/psynet:v13.0.3\n")
                f.write("RUN mkdir /experiment\n")
            
            # Mock the version to be >= 13.1.0
            with patch("psynet.command_line.psynet_version", "13.1.0"):
                with pytest.raises(
                    click.UsageError,
                    match="Your Dockerfile appears to be using an outdated format"
                ):
                    _check_dockerfile_format()
            
            # Test 4: Dockerfile with old format and PsyNet < 13.1.0 - should not raise
            with patch("psynet.command_line.psynet_version", "13.0.3"):
                _check_dockerfile_format()
            
            # Test 5: Dockerfile with old format (master tag) and PsyNet >= 13.1.0 - should raise
            with open("Dockerfile", "w") as f:
                f.write("FROM registry.gitlab.com/psynetdev/psynet:master\n")
                f.write("RUN mkdir /experiment\n")
            
            with patch("psynet.command_line.psynet_version", "13.1.0rc0"):
                with pytest.raises(
                    click.UsageError,
                    match="Your Dockerfile appears to be using an outdated format"
                ):
                    _check_dockerfile_format()
