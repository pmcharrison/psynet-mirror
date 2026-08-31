"""Tests for experiment-local export directory rotation."""

from pathlib import Path
from unittest.mock import Mock

from psynet.experiment import Experiment


def test_export_path_uses_experiment_exports_latest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    path = Path(Experiment.export_path("unused-deployment-id"))

    assert path == tmp_path / "exports" / "latest"
    assert not path.exists()


def test_export_path_moves_previous_latest_to_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    latest = tmp_path / "exports" / "latest"
    latest.mkdir(parents=True)
    (latest / "manifest.json").write_text("{}\n")

    path = Path(Experiment.export_path("unused-deployment-id"))

    assert path == latest
    assert not latest.exists()
    history = list((tmp_path / "exports" / "history").iterdir())
    assert len(history) == 1
    assert (history[0] / "manifest.json").read_text() == "{}\n"


def test_dashboard_export_writes_zip_beside_tree_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "scratch"
    export_dir = root / "export"
    export_dir.mkdir(parents=True)

    def fake_invoke(self, command, **kwargs):
        dest = Path(kwargs["path"])
        (dest / "manifest.json").write_text("{}\n")

    monkeypatch.setattr("click.core.Context.invoke", fake_invoke)

    storage = Mock()
    experiment = Mock()
    experiment.deployment_id = "dep-1"
    experiment.artifact_storage = storage
    experiment.notifier.notify = Mock()
    experiment.notifier.url = Mock(return_value="here")
    experiment.get_artifact_url = Mock(return_value="https://example.test/export.zip")
    monkeypatch.setattr("psynet.experiment.get_experiment", lambda: experiment)

    zip_path = Path(Experiment._export(str(export_dir)))

    assert zip_path == root / "export.zip"
    assert zip_path.is_file()
    assert not (tmp_path / "export.zip").exists()
    storage.upload_export.assert_called_once()
    uploaded = Path(storage.upload_export.call_args.args[0])
    assert uploaded == zip_path
