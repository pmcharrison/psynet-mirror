import json
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner


def _write_archive(path: Path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data/experiment.csv", "id,vars\n1,{}\n")


@pytest.mark.parametrize(
    "value",
    ["gibbs", "village-01", "a1", "0"],
)
def test_validate_local_id_accepts_path_safe_values(value):
    from psynet.local_deployment import validate_local_id

    assert validate_local_id(value) == value


@pytest.mark.parametrize(
    "value",
    ["", "Gibbs", "gibbs experiment", "gibbs/one", "-gibbs", "gibbs_1"],
)
def test_validate_local_id_rejects_unsafe_values(value):
    from psynet.local_deployment import validate_local_id

    with pytest.raises(ValueError, match="lowercase letters, digits, and dashes"):
        validate_local_id(value)


def test_create_snapshot_numbers_archives_and_records_events(tmp_path):
    from psynet.local_deployment import create_snapshot

    def exporter(path):
        _write_archive(path)
        return 12

    first = create_snapshot(
        experiment_path=tmp_path,
        local_id="gibbs",
        reason="periodic",
        deployment_id="launch-1",
        resumed_from=None,
        exporter=exporter,
    )
    second = create_snapshot(
        experiment_path=tmp_path,
        local_id="gibbs",
        reason="shutdown",
        deployment_id="launch-1",
        resumed_from=None,
        exporter=exporter,
    )

    assert first.sequence == 1
    assert first.path == tmp_path / "data/snapshots/gibbs/000001.zip"
    assert second.sequence == 2
    assert second.parent_sequence == 1
    assert second.path == tmp_path / "data/snapshots/gibbs/000002.zip"
    assert not list((tmp_path / "data/snapshots/gibbs").glob("*.partial"))

    metadata = json.loads((tmp_path / "data/snapshots/gibbs/000002.json").read_text())
    assert metadata["reason"] == "shutdown"
    assert metadata["participant_count"] == 12
    assert metadata["parent_sequence"] == 1
    assert len(metadata["sha256"]) == 64

    events = [
        json.loads(line)
        for line in (tmp_path / "data/deployment-events.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events] == [
        "snapshot.succeeded",
        "snapshot.succeeded",
    ]
    assert events[-1]["id"] == "gibbs"
    assert events[-1]["sequence"] == 2


def test_create_snapshot_records_failure_without_partial_archive(tmp_path):
    from psynet.local_deployment import create_snapshot

    def exporter(path):
        path.write_bytes(b"incomplete")
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        create_snapshot(
            experiment_path=tmp_path,
            local_id="gibbs",
            reason="periodic",
            deployment_id="launch-1",
            exporter=exporter,
        )

    assert not list((tmp_path / "data/snapshots/gibbs").glob("*.zip"))
    events = [
        json.loads(line)
        for line in (tmp_path / "data/deployment-events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["event"] == "snapshot.failed"
    assert "database unavailable" in events[-1]["error"]


def test_choose_snapshot_defaults_to_latest_without_a_terminal(tmp_path, monkeypatch):
    from psynet.local_deployment import choose_snapshot, create_snapshot

    def exporter(path):
        _write_archive(path)

    create_snapshot(tmp_path, "gibbs", "periodic", "launch-1", exporter=exporter)
    latest = create_snapshot(
        tmp_path, "gibbs", "shutdown", "launch-1", exporter=exporter
    )
    monkeypatch.setattr("psynet.local_deployment.sys.stdin.isatty", lambda: False)

    assert choose_snapshot(tmp_path, "gibbs").path == latest.path


def test_choose_snapshot_supports_explicit_sequence(tmp_path):
    from psynet.local_deployment import choose_snapshot, create_snapshot

    def exporter(path):
        _write_archive(path)

    first = create_snapshot(
        tmp_path, "gibbs", "periodic", "launch-1", exporter=exporter
    )
    create_snapshot(tmp_path, "gibbs", "shutdown", "launch-1", exporter=exporter)

    assert choose_snapshot(tmp_path, "gibbs", "1").path == first.path
    with pytest.raises(ValueError, match="Snapshot 9 does not exist"):
        choose_snapshot(tmp_path, "gibbs", "9")


def test_deploy_local_requires_id(tmp_path):
    from psynet.command_line import psynet
    from psynet.utils import working_directory

    (tmp_path / "experiment.py").write_text("")
    runner = CliRunner()
    with working_directory(tmp_path):
        result = runner.invoke(psynet, ["deploy", "local"])

    assert result.exit_code == 2
    assert "Missing option '--id'" in result.output


def test_comment_writes_event_for_explicit_id(tmp_path):
    from psynet.command_line import psynet
    from psynet.utils import working_directory

    (tmp_path / "experiment.py").write_text("")
    runner = CliRunner()
    with working_directory(tmp_path):
        result = runner.invoke(
            psynet,
            ["comment", "--id", "gibbs", "Changed headphones."],
        )

    assert result.exit_code == 0, result.output
    event = json.loads((tmp_path / "data/deployment-events.jsonl").read_text().strip())
    assert event["event"] == "comment"
    assert event["id"] == "gibbs"
    assert event["text"] == "Changed headphones."


@pytest.mark.parametrize("signal_shutdown", [False, True])
def test_deploy_local_restores_selected_snapshot_and_saves_shutdown(
    tmp_path, monkeypatch, signal_shutdown
):
    from psynet.command_line import psynet
    from psynet.local_deployment import DatabaseOwner, Snapshot
    from psynet.utils import working_directory

    (tmp_path / "experiment.py").write_text("")
    archive = tmp_path / "data/snapshots/gibbs/000004.zip"
    archive.parent.mkdir(parents=True)
    _write_archive(archive)
    selected = Snapshot(
        sequence=4,
        path=archive,
        metadata_path=archive.with_suffix(".json"),
        created_at="2026-08-27T18:00:00Z",
        reason="periodic",
        deployment_id="old-launch",
        parent_sequence=3,
        participant_count=12,
        sha256=None,
    )
    final = Snapshot(
        sequence=5,
        path=archive.with_name("000005.zip"),
        metadata_path=archive.with_name("000005.json"),
        created_at="2026-08-27T18:10:00Z",
        reason="shutdown",
        deployment_id="new-launch",
        parent_sequence=4,
        participant_count=13,
        sha256=None,
    )
    calls = {}
    events = []

    @contextmanager
    def unlocked(*_args):
        yield

    def run_local(*args, **kwargs):
        calls["run"] = (args, kwargs)
        if signal_shutdown:
            raise SystemExit(0)

    def create_final(*args, **kwargs):
        calls["snapshot"] = (args, kwargs)
        return final

    monkeypatch.setattr("psynet.command_line.local_deployment_lock", unlocked)
    monkeypatch.setattr("psynet.services.ensure_local_services", lambda **_kwargs: True)
    monkeypatch.setattr(
        "psynet.command_line.protect_existing_database", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "psynet.command_line.choose_snapshot",
        lambda *_args, **_kwargs: selected,
    )
    monkeypatch.setattr("psynet.command_line._run_local", run_local)
    monkeypatch.setattr(
        "psynet.command_line.read_database_owner",
        lambda: DatabaseOwner("gibbs", tmp_path, "new-launch", "Example"),
    )
    monkeypatch.setattr("psynet.command_line.create_snapshot", create_final)
    monkeypatch.setattr(
        "psynet.command_line.append_deployment_event",
        lambda *args, **kwargs: events.append((args, kwargs)),
    )

    with working_directory(tmp_path):
        result = CliRunner().invoke(
            psynet,
            ["deploy", "local", "--id", "gibbs", "--snapshot", "latest"],
        )

    assert result.exit_code == 0, result.output
    assert calls["run"][0][2] == str(archive)
    assert calls["run"][1]["local_id"] == "gibbs"
    assert calls["run"][1]["resumed_from"] == 4
    assert calls["snapshot"][1]["reason"] == "shutdown"
    assert calls["snapshot"][1]["resumed_from"] == 4
    assert [args[1] for args, _kwargs in events] == [
        "deploy.requested",
        "deploy.stopped",
    ]


def test_protect_existing_database_recovers_interrupted_owner(tmp_path, monkeypatch):
    from psynet.local_deployment import (
        DatabaseOwner,
        Snapshot,
        protect_existing_database,
    )

    owner_path = tmp_path / "owner"
    owner_path.mkdir()
    recovered = Mock(spec=Snapshot)
    create_snapshot = Mock(return_value=recovered)
    monkeypatch.setattr(
        "psynet.local_deployment.read_database_owner",
        lambda: DatabaseOwner("first", owner_path, "launch-1", "Example"),
    )
    monkeypatch.setattr("psynet.local_deployment.list_snapshots", lambda *_args: [])
    monkeypatch.setattr(
        "psynet.local_deployment.create_snapshot",
        create_snapshot,
    )

    result = protect_existing_database(tmp_path / "new", "second")

    assert result is recovered
    create_snapshot.assert_called_once_with(
        owner_path,
        "first",
        reason="recovery-before-reset",
        deployment_id="launch-1",
    )


def test_protect_existing_database_skips_clean_shutdown(tmp_path, monkeypatch):
    from psynet.local_deployment import (
        DatabaseOwner,
        Snapshot,
        protect_existing_database,
    )

    owner_path = tmp_path / "owner"
    owner_path.mkdir()
    latest = Mock(spec=Snapshot, reason="shutdown", deployment_id="launch-1")
    monkeypatch.setattr(
        "psynet.local_deployment.read_database_owner",
        lambda: DatabaseOwner("first", owner_path, "launch-1", "Example"),
    )
    monkeypatch.setattr(
        "psynet.local_deployment.list_snapshots", lambda *_args: [latest]
    )
    create_snapshot = Mock()
    monkeypatch.setattr(
        "psynet.local_deployment.create_snapshot",
        create_snapshot,
    )

    assert protect_existing_database(tmp_path / "new", "second") is None
    create_snapshot.assert_not_called()
