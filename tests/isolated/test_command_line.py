import hashlib
import json
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pandas as pd
import pytest
from click.testing import CliRunner

from psynet.command_line import (
    _check_constraints,
    _create_sql_profile_run_dir,
    _enable_sql_profile,
    check_dockerfile,
    update_scripts_,
)
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

    def test_dev_changelog_dispatches_to_builder(self, monkeypatch, tmp_path):
        from psynet.command_line import psynet
        from psynet.dev import changelog as changelog_module

        calls = []

        fragments_dir = tmp_path / "changelog.d"
        fragments_dir.mkdir()
        changelog_path = tmp_path / "CHANGELOG.md"
        changelog_path.write_text("# CHANGELOG\n", encoding="utf-8")

        monkeypatch.setattr(changelog_module, "FRAGMENTS_DIR", fragments_dir)
        monkeypatch.setattr(changelog_module, "CHANGELOG_PATH", changelog_path)
        monkeypatch.setattr(
            changelog_module,
            "new_command",
            lambda c, d: calls.append(("new", c, d)) or 0,
        )
        monkeypatch.setattr(
            changelog_module,
            "release_command",
            lambda v, d: calls.append(("release", v, d)) or 0,
        )
        monkeypatch.setattr(
            changelog_module,
            "build_command",
            lambda: calls.append(("build",)) or 0,
        )
        monkeypatch.setattr(
            changelog_module,
            "check_mr_command",
            lambda b, h: calls.append(("check-mr", b, h)) or 0,
        )

        runner = CliRunner()

        result = runner.invoke(
            psynet, ["dev", "changelog", "new", "fixed", "Fix thing"]
        )
        assert result.exit_code == 0, result.output
        assert calls == [("new", "fixed", "Fix thing")]

        result = runner.invoke(
            psynet,
            ["dev", "changelog", "release", "13.2.0", "2026-03-13"],
        )
        assert result.exit_code == 0, result.output
        assert calls[-1] == ("release", "13.2.0", "2026-03-13")

        result = runner.invoke(psynet, ["dev", "changelog", "preview"])
        assert result.exit_code == 0, result.output
        assert calls[-1] == ("build",)

        result = runner.invoke(psynet, ["dev", "changelog", "check-mr", "base", "head"])
        assert result.exit_code == 0, result.output
        assert calls[-1] == ("check-mr", "base", "head")

    def test_dev_changelog_check_mr_is_hidden_from_help(self):
        result = subprocess.run(
            ["psynet", "dev", "changelog", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "check-mr" not in result.stdout

    def test_dev_changelog_requires_source_checkout(self, tmp_path):
        from psynet.command_line import psynet

        runner = CliRunner()
        with working_directory(tmp_path):
            result = runner.invoke(psynet, ["dev", "changelog", "preview"])

        assert result.exit_code != 0
        assert "Run from a PsyNet source checkout" in result.output

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


def _setup_basic_data_export(monkeypatch, basic_data):
    class DummyExperiment:
        def get_basic_data(self, context=None, **kwargs):
            assert context == "export"
            return basic_data

    def fake_get_experiment():
        return DummyExperiment()

    @contextmanager
    def dummy_spinner(*args, **kwargs):
        class Spinner:
            def ok(self, *_args, **_kwargs):
                return None

        yield Spinner()

    monkeypatch.setattr("psynet.experiment.get_experiment", fake_get_experiment)
    monkeypatch.setattr(
        "psynet.command_line.dump_db_to_disk", lambda *args, **kwargs: None
    )
    monkeypatch.setattr("psynet.command_line.yaspin", dummy_spinner)


@pytest.fixture
def run_basic_data_export(tmp_path):
    from psynet.command_line import export_data

    def _run(anonymize):
        export_path = tmp_path / "export"
        export_path.mkdir()
        export_data(
            local=True,
            anonymize=anonymize,
            database_zip_path=str(tmp_path / "database.zip"),
            export_path=str(export_path),
        )
        return export_path

    return _run


def test_export_data_writes_basic_data_json(monkeypatch, run_basic_data_export):
    basic_data = {"participant": [{"id": 1}]}
    _setup_basic_data_export(monkeypatch, basic_data)
    export_path = run_basic_data_export(anonymize=True)

    basic_data_path = export_path / "anonymous" / "basic_data.json"
    assert basic_data_path.exists()
    with open(basic_data_path, "r") as file:
        assert json.load(file) == basic_data


def test_export_data_skips_basic_data_when_none(monkeypatch, run_basic_data_export):
    _setup_basic_data_export(monkeypatch, None)
    export_path = run_basic_data_export(anonymize=True)

    basic_data_json = export_path / "anonymous" / "basic_data.json"
    basic_data_zip = export_path / "anonymous" / "basic_data.zip"
    assert not basic_data_json.exists()
    assert not basic_data_zip.exists()


def test_export_data_writes_basic_data_folder_for_dataframes(
    monkeypatch, run_basic_data_export
):
    basic_data = {
        "participant": pd.DataFrame([{"id": 1}]),
        "trial": pd.DataFrame([{"id": 2, "answer": "ok"}]),
    }
    _setup_basic_data_export(monkeypatch, basic_data)
    export_path = run_basic_data_export(anonymize=False)

    basic_data_dir = export_path / "regular" / "basic_data"
    assert basic_data_dir.exists()
    assert sorted(path.name for path in basic_data_dir.iterdir()) == [
        "participant.csv",
        "trial.csv",
    ]


def test_export_data_sanitizes_basic_data_dataframe_keys(
    monkeypatch, run_basic_data_export
):
    basic_data = {
        "trial/results": pd.DataFrame([{"id": 1}]),
        "trial results": pd.DataFrame([{"id": 2}]),
    }
    _setup_basic_data_export(monkeypatch, basic_data)
    export_path = run_basic_data_export(anonymize=False)

    basic_data_dir = export_path / "regular" / "basic_data"
    assert basic_data_dir.exists()
    assert sorted(path.name for path in basic_data_dir.iterdir()) == [
        "trial_results.csv",
        "trial_results_2.csv",
    ]


def test_export_data_avoids_suffix_filename_collisions(
    monkeypatch, run_basic_data_export
):
    basic_data = {
        "trial": pd.DataFrame([{"id": 1}]),
        "trial_2": pd.DataFrame([{"id": 2}]),
        "trial/": pd.DataFrame([{"id": 3}]),
    }
    _setup_basic_data_export(monkeypatch, basic_data)
    export_path = run_basic_data_export(anonymize=False)

    basic_data_dir = export_path / "regular" / "basic_data"
    assert basic_data_dir.exists()
    assert sorted(path.name for path in basic_data_dir.iterdir()) == [
        "trial.csv",
        "trial_2.csv",
        "trial_3.csv",
    ]


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


def test_check_dockerfile():
    """Test that check_dockerfile detects missing and outdated Dockerfiles."""
    with tempfile.TemporaryDirectory() as dir:
        with working_directory(dir):
            # Test 1: No Dockerfile - should raise
            with pytest.raises(
                click.UsageError,
                match="Docker deployments require a Dockerfile",
            ):
                check_dockerfile()

            # Test 2: Dockerfile with new format - should not raise
            # Use update_scripts_ to generate a proper Dockerfile
            with patch("click.echo"):  # Suppress output
                update_scripts_()
            check_dockerfile()

            # Test 3: Dockerfile with old format (version tag) - should raise
            with open("Dockerfile", "w") as f:
                f.write("FROM registry.gitlab.com/psynetdev/psynet:v13.0.3\n")
                f.write("RUN mkdir /experiment\n")

            with pytest.raises(
                click.UsageError,
                match="Your Dockerfile appears to be using an outdated format",
            ):
                check_dockerfile()

            # Test 4: Dockerfile with old format (master tag) - should raise
            with open("Dockerfile", "w") as f:
                f.write("FROM registry.gitlab.com/psynetdev/psynet:master\n")
                f.write("RUN mkdir /experiment\n")

            with pytest.raises(
                click.UsageError,
                match="Your Dockerfile appears to be using an outdated format",
            ):
                check_dockerfile()


def test_enable_sql_profile_uses_unique_run_subdirectories(tmp_path, monkeypatch):
    monkeypatch.delenv("PSYNET_SQL_PROFILE", raising=False)
    monkeypatch.delenv("PSYNET_SQL_PROFILE_DIR", raising=False)
    monkeypatch.delenv("PSYNET_SQL_PROFILE_SILENT", raising=False)

    parent_dir = tmp_path / "profiles"
    profile_dir_1, keep_dir_1 = _enable_sql_profile(None, str(parent_dir))
    profile_dir_2, keep_dir_2 = _enable_sql_profile(None, str(parent_dir))

    assert keep_dir_1 is True
    assert keep_dir_2 is True
    assert profile_dir_1 != profile_dir_2
    assert Path(profile_dir_1).parent == parent_dir
    assert Path(profile_dir_2).parent == parent_dir
    assert Path(profile_dir_1).is_dir()
    assert Path(profile_dir_2).is_dir()


def test_create_sql_profile_run_dir_with_custom_parent(tmp_path):
    parent_dir = tmp_path / "profiles"

    profile_dir_1, keep_dir_1 = _create_sql_profile_run_dir(str(parent_dir))
    profile_dir_2, keep_dir_2 = _create_sql_profile_run_dir(str(parent_dir))

    assert keep_dir_1 is True
    assert keep_dir_2 is True
    assert profile_dir_1 != profile_dir_2
    assert Path(profile_dir_1).parent == parent_dir
    assert Path(profile_dir_2).parent == parent_dir


def test_create_sql_profile_run_dir_without_custom_parent():
    profile_dir, keep_dir = _create_sql_profile_run_dir(None)

    assert keep_dir is False
    assert Path(profile_dir).is_dir()
    assert Path(profile_dir).name.startswith("psynet-sql-profile-")


def test_start_local_server_uses_debug_local_subprocess():
    from psynet.command_line import _start_local_server_and_wait_for_ready, _stop_server

    process = Mock()
    process.expect_exact.return_value = None
    process.isalive.return_value = False

    with patch("psynet.command_line.pexpect.spawn", return_value=process) as spawn:
        server_info = _start_local_server_and_wait_for_ready(debug=False, max_wait=5)

    assert server_info["process"] is process
    args, kwargs = spawn.call_args
    assert args == ("psynet", ["debug", "local", "--legacy", "--no-browsers"])
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["env"]["SKIP_DEPENDENCY_CHECK"] == "1"
    assert kwargs["env"]["BROWSER"] == "true"
    _stop_server(server_info)


def test_stop_server_gracefully_stops_debug_subprocess():
    from psynet.command_line import _stop_server

    process = Mock()
    process.isalive.return_value = True
    process.expect_exact.return_value = None
    log_file = Mock()

    server_info = {
        "process": process,
        "tmp_log_path": "/tmp/psynet_server_test.log",
        "log_file": log_file,
    }

    with patch("psynet.command_line.kill_psynet_worker_processes") as kill_workers:
        _stop_server(server_info)

    process.sendcontrol.assert_called_once_with("c")
    process.expect_exact.assert_called()
    process.close.assert_called_once()
    log_file.close.assert_called_once()
    kill_workers.assert_called_once()


def test_run_performance_test_with_new_server_loads_runtime_server_config():
    from psynet.command_line import _run_performance_test_with_new_server

    process = Mock()
    config = Mock()
    config.ready = True
    server_info = {
        "process": process,
        "tmp_log_path": "/tmp/psynet_server_test.log",
        "log_file": Mock(),
    }

    with (
        patch(
            "psynet.command_line._start_local_server_and_wait_for_ready",
            return_value=server_info,
        ),
        patch("psynet.command_line.get_config", return_value=config),
        patch(
            "psynet.command_line.redis_vars.get",
            return_value="/tmp/dallinger_develop/exp",
        ),
        patch("psynet.command_line._run_performance_test_with_existing_server"),
        patch("psynet.command_line._stop_server"),
    ):
        _run_performance_test_with_new_server(
            n_bots="2", stagger=0.1, time_factor=1.0, duration_minutes=0.5, debug=False
        )

    config.load_from_file.assert_called_once_with(
        "/tmp/dallinger_develop/exp/config.txt"
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        (True, True),
        (False, False),
        (42, 42),
        ("hello", "hello"),
        (3.14, 3.14),
        (0.0, 0.0),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (Decimal("1.5"), 1.5),
        (datetime(2025, 5, 7, 12, 30, 45), "2025-05-07T12:30:45"),
        (date(2025, 5, 7), "2025-05-07"),
        ((1, 2, 3), [1, 2, 3]),
    ],
)
def test_to_json_safe_scalars_and_simple_collections(value, expected):
    from psynet.perf_test import _to_json_safe

    assert _to_json_safe(value) == expected


def test_to_json_safe_decimal_returns_float_type():
    # `Decimal == float` compares by value; pin the type explicitly.
    from psynet.perf_test import _to_json_safe

    assert isinstance(_to_json_safe(Decimal("1.5")), float)


def test_to_json_safe_set_and_frozenset_are_sorted_lists():
    # Output must be deterministic so repeated runs produce identical JSON
    # (otherwise git diffs of stored results are noisy).
    from psynet.perf_test import _to_json_safe

    assert _to_json_safe({3, 1, 2}) == [1, 2, 3]
    assert _to_json_safe(frozenset({"b", "a", "c"})) == ["a", "b", "c"]


def test_to_json_safe_mixed_type_set_falls_back_to_unsorted_list():
    # Heterogeneous sets aren't sortable across types; the helper must still
    # return a list rather than raising.
    from psynet.perf_test import _to_json_safe

    result = _to_json_safe({1, "a", None})
    assert isinstance(result, list)
    assert set(result) == {1, "a", None}


def test_to_json_safe_recurses_through_nested_dict_and_list():
    from psynet.perf_test import _to_json_safe

    nested = {
        "rows": [
            {"value": Decimal("0.5"), "missing": float("nan")},
            {"value": Decimal("0.75"), "missing": None},
        ],
    }
    assert _to_json_safe(nested) == {
        "rows": [
            {"value": 0.5, "missing": None},
            {"value": 0.75, "missing": None},
        ],
    }


def test_collect_run_metadata_includes_environment_fields():
    from psynet.command_line import _collect_run_metadata

    metadata = _collect_run_metadata("my-experiment")
    assert metadata["experiment_label"] == "my-experiment"
    for key in ("psynet_version", "dallinger_version", "python_version", "platform"):
        assert isinstance(metadata[key], str) and metadata[key]


def test_write_json_results_emits_expected_schema_with_coerced_values(tmp_path):
    from psynet.command_line import _write_json_results

    json_output = str(tmp_path / "results.json")
    metadata = {
        "psynet_version": "13.2.0a0",
        "dallinger_version": "12.2.0",
        "python_version": "3.13.9",
        "platform": "Linux-test",
        "experiment_label": "static_big",
        "started_at": "2026-05-07T14:23:11",
        "finished_at": "2026-05-07T14:25:42",
    }
    options = {
        "n_bots_sweep": [1, 2],
        "duration_minutes": 1.5,
        "stagger_interval_s": 0.1,
        "time_factor": 1.0,
    }
    all_results = [
        {
            "n_bots": 1,
            "avg_latency": Decimal("0.5"),
            "nan_value": float("nan"),
            "inf_value": float("inf"),
            "process_stats": [{"avg": Decimal("0.001"), "max": float("nan")}],
        },
        {"n_bots": 2, "avg_latency": Decimal("0.6")},
    ]

    _write_json_results(
        json_output, metadata=metadata, options=options, all_results=all_results
    )

    with open(json_output) as f:
        payload = json.load(f)

    assert payload["schema_version"] == 1
    for key, expected in metadata.items():
        assert payload[key] == expected
    assert payload["options"] == options
    assert len(payload["results"]) == 2

    first = payload["results"][0]
    assert first["avg_latency"] == 0.5
    assert first["nan_value"] is None
    assert first["inf_value"] is None
    assert first["process_stats"][0]["avg"] == 0.001
    assert first["process_stats"][0]["max"] is None
