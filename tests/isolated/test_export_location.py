"""Tests for experiment-local export directory rotation."""

from pathlib import Path

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
