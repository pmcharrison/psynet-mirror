import os
import pytest
import subprocess
import mock
from mock import patch
from click.testing import CliRunner


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


class TestDebug():
    @pytest.fixture
    def debug(self):
        from psynet.command_line import debug
        return debug

    @pytest.fixture
    def prepare(self):
        with mock.patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_debug(self):
        with mock.patch("psynet.command_line.dallinger_debug") as mock_dallinger_debug:
            yield mock_dallinger_debug

    def test_debug(self, debug, prepare, dallinger_debug):
        result = CliRunner().invoke(debug, [])
        prepare.assert_called_once_with(force=False)
        dallinger_debug.assert_called_once_with(verbose=False, bot=False, proxy=None, no_browsers=False)

    def test_debug_all_non_default(self, debug, prepare, dallinger_debug):
        result = CliRunner().invoke(debug, ["--verbose", "--bot", "--proxy=5001", "--no-browsers", "--force-prepare"])
        prepare.assert_called_once_with(force=True)
        dallinger_debug.assert_called_once_with(verbose=True, bot=True, proxy="5001", no_browsers=True)


class TestDeploy():
    @pytest.fixture
    def deploy(self):
        from psynet.command_line import deploy
        return deploy

    @pytest.fixture
    def prepare(self):
        with mock.patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_deploy(self):
        with mock.patch("psynet.command_line.dallinger_deploy") as mock_dallinger_deploy:
            yield mock_dallinger_deploy

    def test_deploy(self, deploy, prepare, dallinger_deploy):
        result = CliRunner().invoke(deploy, [])
        prepare.assert_called_once_with(force=False)
        dallinger_deploy.assert_called_once_with(verbose=False, app=None, archive=None)

    def test_deploy_all_non_default(self, deploy, prepare, dallinger_deploy):
        result = CliRunner().invoke(deploy, ["--verbose", "--app=some_app_name", "--archive=/path/to/some_archive", "--force-prepare"])
        prepare.assert_called_once_with(force=True)
        dallinger_deploy.assert_called_once_with(verbose=True, app='some_app_name', archive='/path/to/some_archive')


class TestSandbox():
    @pytest.fixture
    def sandbox(self):
        from psynet.command_line import sandbox
        return sandbox

    @pytest.fixture
    def prepare(self):
        with mock.patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_sandbox(self):
        with mock.patch("psynet.command_line.dallinger_sandbox") as mock_dallinger_sandbox:
            yield mock_dallinger_sandbox

    def test_sandbox(self, sandbox, prepare, dallinger_sandbox):
        result = CliRunner().invoke(sandbox, [])
        prepare.assert_called_once_with(force=False)
        dallinger_sandbox.assert_called_once_with(verbose=False, app=None, archive=None)

    def test_sandbox_all_non_default(self, sandbox, prepare, dallinger_sandbox):
        result = CliRunner().invoke(sandbox, ["--verbose", "--app=some_app_name", "--archive=/path/to/some_archive", "--force-prepare"])
        prepare.assert_called_once_with(force=True)
        dallinger_sandbox.assert_called_once_with(verbose=True, app='some_app_name', archive='/path/to/some_archive')


@pytest.mark.usefixtures("demo_non_adaptive")
class TestEstimate():
    @pytest.fixture
    def estimate(self):
        from psynet.command_line import estimate
        return estimate

    @pytest.fixture
    def prepare(self):
        with mock.patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def import_local_experiment(self):
        with mock.patch("psynet.command_line.import_local_experiment") as mock_import_local_experiment:
            yield mock_import_local_experiment

    def test_estimate(self,
                      estimate,
                      import_local_experiment,
                      prepare):
        result = CliRunner().invoke(estimate, [])
        prepare.assert_not_called()
        import_local_experiment.assert_called_once()


@pytest.mark.usefixtures("demo_non_adaptive")
class TestExport():
    @pytest.fixture
    def export(self):
        from psynet.command_line import export
        return export

    @pytest.fixture
    def prepare(self):
        with mock.patch("psynet.command_line.prepare") as mock_prepare:
            yield mock_prepare

    @pytest.fixture
    def dallinger_data_export(self):
        with mock.patch("psynet.command_line.dallinger_data.export") as mock_dallinger_data_export:
            yield mock_dallinger_data_export

    @pytest.fixture
    def import_local_experiment(self):
        with mock.patch("psynet.command_line.import_local_experiment") as mock_import_local_experiment:
            yield mock_import_local_experiment

    @pytest.fixture
    def create_export_dirs(self):
        with mock.patch("psynet.command_line.create_export_dirs") as mock_create_export_dirs:
            yield mock_create_export_dirs

    @pytest.fixture
    def move_snapshot_file(self):
        with mock.patch("psynet.command_line.move_snapshot_file") as mock_move_snapshot_file:
            yield mock_move_snapshot_file

    @pytest.fixture
    def get_base_url(self):
        with mock.patch("psynet.command_line.get_base_url") as mock_get_base_url:
            yield mock_get_base_url

    @pytest.fixture
    def export_data(self):
        with mock.patch("psynet.command_line.export_data") as mock_export_data:
            yield mock_export_data

    @pytest.fixture
    def requests_get(self):
        response = mock.Mock()
        response.content.decode.return_value = '{"SomeClass": 123}'
        with mock.patch("psynet.command_line.requests.get") as mocḱ_requests_get:
            mocḱ_requests_get.return_value = response
            yield mocḱ_requests_get

    def test_export_missing_app_param(self, export):
        output = CliRunner().invoke(export)
        assert b"Usage: export [OPTIONS]" in output.output_bytes
        assert b'Error: Missing option "--app".' in output.output_bytes
        assert output.exit_code == 2

    def test_export_local(self, export, prepare, move_snapshot_file, dallinger_data_export, get_base_url):
        result = CliRunner().invoke(export, ["--local", "--app=app-1"])
        prepare.assert_not_called()
        move_snapshot_file.assert_called_once_with("data/data-app-1", "app-1")
        dallinger_data_export.assert_called_once_with("app-1", local=True)
        get_base_url.assert_called_once()

    def test_export_remote(self, export, prepare, move_snapshot_file, dallinger_data_export, get_base_url):
        result = CliRunner().invoke(export, ["--app=app-1"])
        prepare.assert_not_called()
        move_snapshot_file.assert_called_once_with("data/data-app-1", "app-1")
        dallinger_data_export.assert_called_once_with("app-1", local=False)
        get_base_url.assert_not_called()

    def test_export(self,
                    export,
                    import_local_experiment,
                    create_export_dirs,
                    dallinger_data_export,
                    move_snapshot_file,
                    requests_get,
                    export_data):
        result = CliRunner().invoke(export, ["--app=app-1"])
        import_local_experiment.assert_called_once()
        create_export_dirs.assert_called_once_with("data/data-app-1")
        dallinger_data_export.assert_called_once_with("app-1", local=False)
        move_snapshot_file.assert_called_once_with("data/data-app-1", "app-1")
        assert requests_get.call_count == 9
        assert export_data.call_count == 9
        export_data.assert_called_with("some_class", "data/data-app-1", 123)
        assert result.exit_code == 0
