"""Tests for client-side export transport, hydration, and identity checks."""

import csv
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from psynet.export.client import (
    AssetTransferPlan,
    TransferError,
    choose_transport,
    hydrate_assets,
    plan_asset_transfer,
    publish_export,
)
from psynet.export.identity import (
    ProjectIdentity,
    ProjectMismatch,
    confirm_project_identity,
)
from psynet.utils import sha256_directory


@pytest.fixture()
def cache_root(tmp_path):
    return tmp_path / "cache"


def _write_remote_object(root: Path, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    dest = root / "objects" / "sha256" / digest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)
    return digest


def _write_remote_folder(root: Path, files: dict[str, bytes]) -> str:
    staging = root / "_src"
    staging.mkdir(parents=True)
    for name, payload in files.items():
        (staging / name).write_bytes(payload)
    digest = sha256_directory(staging)
    dest = root / "objects" / "sha256" / digest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staging, dest)
    shutil.rmtree(staging)
    return digest


def _rsync_double(remote_root: Path, calls: list):
    """Copy ``--files-from`` paths without requiring an ``rsync`` binary."""

    def run(cmd, check=False, **kwargs):
        calls.append(cmd)
        files_from = Path(cmd[cmd.index("--files-from") + 1])
        dest = Path(str(cmd[-1]).rstrip("/"))
        for rel in files_from.read_text().splitlines():
            if not rel:
                continue
            src = remote_root / rel
            if not src.exists():
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                shutil.copy2(src, target)
        return subprocess.CompletedProcess(cmd, 0)

    return run


def _write_asset_manifest(export_dir: Path, rows: list[dict]) -> None:
    assets = export_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "type",
        "export_path",
        "sha256_contents",
        "is_folder",
        "storage",
    ]
    with (assets / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


###############
#  transport  #
###############


def test_incremental_transfer_is_used_only_when_the_deployment_supports_it():
    eligible = ProjectIdentity(incremental_asset_modes=("none", "collected"))
    s3_backed = ProjectIdentity(incremental_asset_modes=("none",))

    assert (
        choose_transport(eligible, assets="collected", over_ssh=True) == "incremental"
    )
    assert choose_transport(s3_backed, assets="collected", over_ssh=True) == "archive"
    assert choose_transport(eligible, assets="all", over_ssh=True) == "archive"
    # No SSH access, and deployments without a preflight, use the archive.
    assert choose_transport(eligible, assets="collected", over_ssh=False) == "archive"
    assert choose_transport(None, assets="collected", over_ssh=True) == "archive"
    # --assets none never needs asset bytes, so the core snapshot suffices.
    assert choose_transport(s3_backed, assets="none", over_ssh=True) == "incremental"


def test_explicit_incremental_request_reports_an_unsupported_selection():
    identity = ProjectIdentity(incremental_asset_modes=("none",))

    assert (
        choose_transport(
            identity, assets="collected", over_ssh=True, requested="archive"
        )
        == "archive"
    )
    with pytest.raises(TransferError):
        choose_transport(
            identity, assets="collected", over_ssh=True, requested="incremental"
        )


def test_asset_plan_excludes_assets_rsync_cannot_supply(tmp_path):
    _write_asset_manifest(
        tmp_path,
        [
            {
                "id": 1,
                "type": "experiment_asset",
                "export_path": "a.wav",
                "sha256_contents": "a" * 64,
                "storage": "LocalStorage",
            },
            {"id": 2, "type": "external_asset", "export_path": "b.wav"},
            {
                "id": 3,
                "type": "experiment_asset",
                "export_path": "c.wav",
                "sha256_contents": "c" * 64,
                "storage": "S3Storage",
            },
            {
                "id": 4,
                "type": "on_demand_asset",
                "export_path": "d.wav",
                "sha256_contents": "d" * 64,
                "storage": "LocalStorage",
            },
        ],
    )

    plan = plan_asset_transfer(str(tmp_path))

    assert plan.digests == ["a" * 64]
    assert [row["id"] for row in plan.ineligible] == ["3", "4"]
    assert not plan.eligible


def test_hydration_reports_a_failed_rsync_as_a_transfer_error(
    tmp_path, cache_root, monkeypatch
):
    """A failed rsync must be recoverable, so the caller can fall back."""
    remote = tmp_path / "remote"
    digest = _write_remote_object(remote, b"recording-bytes")

    def run(cmd, check=False, **kwargs):
        # Exit 23 is what rsync returns when it cannot read some source files,
        # for example an asset folder the SSH user has no permission on.
        raise subprocess.CalledProcessError(23, cmd)

    monkeypatch.setattr("psynet.export.ssh_rsync.subprocess.run", run)

    export_dir = tmp_path / "export"
    _write_asset_manifest(
        export_dir,
        [
            {
                "id": 1,
                "type": "experiment_asset",
                "export_path": "a.wav",
                "sha256_contents": digest,
                "storage": "LocalStorage",
            }
        ],
    )

    with pytest.raises(TransferError, match="exit code 23"):
        hydrate_assets(
            str(export_dir),
            plan_asset_transfer(str(export_dir)),
            rsync_source=str(remote),
            cache_root=cache_root,
        )


def test_hydration_fetches_missing_objects_once_and_reuses_the_cache(
    tmp_path, cache_root, monkeypatch
):
    remote = tmp_path / "remote"
    file_digest = _write_remote_object(remote, b"recording-bytes")
    folder_digest = _write_remote_folder(remote, {"part.txt": b"folder-bytes"})

    calls = []
    monkeypatch.setattr(
        "psynet.export.ssh_rsync.subprocess.run", _rsync_double(remote, calls)
    )

    def build_export(name):
        export_dir = tmp_path / name
        _write_asset_manifest(
            export_dir,
            [
                {
                    "id": 1,
                    "type": "experiment_asset",
                    "export_path": "module/a.wav",
                    "sha256_contents": file_digest,
                    "storage": "LocalStorage",
                },
                {
                    "id": 2,
                    "type": "experiment_asset",
                    "export_path": "module/folder",
                    "sha256_contents": folder_digest,
                    "is_folder": "True",
                    "storage": "LocalStorage",
                },
            ],
        )
        return export_dir

    cold = build_export("cold")
    assert (
        hydrate_assets(
            str(cold),
            plan_asset_transfer(str(cold)),
            rsync_source=str(remote),
            cache_root=cache_root,
        )
        == 2
    )
    assert (cold / "assets" / "module" / "a.wav").read_bytes() == b"recording-bytes"
    assert (
        cold / "assets" / "module" / "folder" / "part.txt"
    ).read_bytes() == b"folder-bytes"
    assert len(calls) == 1

    warm = build_export("warm")
    assert (
        hydrate_assets(
            str(warm),
            plan_asset_transfer(str(warm)),
            rsync_source=str(remote),
            cache_root=cache_root,
        )
        == 2
    )
    # A warm cache transfers nothing.
    assert len(calls) == 1


def test_hydration_fails_when_transferred_bytes_do_not_match_their_digest(
    tmp_path, cache_root, monkeypatch
):
    remote = tmp_path / "remote"
    claimed_digest = hashlib.sha256(b"expected").hexdigest()
    dest = remote / "objects" / "sha256" / claimed_digest
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"tampered")

    monkeypatch.setattr(
        "psynet.export.ssh_rsync.subprocess.run", _rsync_double(remote, [])
    )
    export_dir = tmp_path / "export"
    _write_asset_manifest(
        export_dir,
        [
            {
                "id": 1,
                "type": "experiment_asset",
                "export_path": "a.wav",
                "sha256_contents": claimed_digest,
                "storage": "LocalStorage",
            }
        ],
    )

    with pytest.raises(TransferError, match="still missing"):
        hydrate_assets(
            str(export_dir),
            plan_asset_transfer(str(export_dir)),
            rsync_source=str(remote),
            cache_root=cache_root,
        )


def test_hydration_refuses_an_ineligible_plan(tmp_path):
    with pytest.raises(TransferError):
        hydrate_assets(
            str(tmp_path),
            AssetTransferPlan(rows=[], digests=[], ineligible=[{"id": 1}]),
            rsync_source="unused",
        )


################
#  publishing  #
################


def test_publishing_replaces_the_destination_atomically(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text("new")
    destination = tmp_path / "exports" / "latest"
    destination.mkdir(parents=True)
    (destination / "manifest.json").write_text("old")

    published = publish_export(str(staging), str(destination))

    assert Path(published) == destination
    assert (destination / "manifest.json").read_text() == "new"
    assert not staging.exists()
    assert list(tmp_path.joinpath("exports").iterdir()) == [destination]


def test_publishing_uses_the_history_rotation_hook_when_provided(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text("new")
    destination = tmp_path / "latest"
    destination.mkdir()
    (destination / "manifest.json").write_text("old")
    archived = []

    def rotate(path):
        target = tmp_path / "history"
        Path(path).rename(target)
        archived.append(str(target))
        return str(target)

    publish_export(str(staging), str(destination), rotate_history=rotate)

    assert archived == [str(tmp_path / "history")]
    assert (tmp_path / "history" / "manifest.json").read_text() == "old"
    assert (destination / "manifest.json").read_text() == "new"


def test_publishing_nothing_leaves_the_destination_untouched(tmp_path):
    destination = tmp_path / "latest"
    destination.mkdir()
    (destination / "manifest.json").write_text("old")

    with pytest.raises(TransferError):
        publish_export(str(tmp_path / "missing-staging"), str(destination))

    assert (destination / "manifest.json").read_text() == "old"


##############
#  identity  #
##############


def test_wrong_experiment_directory_blocks_before_any_transfer():
    local = ProjectIdentity(experiment_label="my-demo", export_format_version=1)
    remote = ProjectIdentity(experiment_label="other-demo", export_format_version=1)

    with pytest.raises(ProjectMismatch, match="wrong experiment folder"):
        confirm_project_identity(local, remote)


def test_unreadable_export_format_is_a_hard_error():
    local = ProjectIdentity(experiment_label="my-demo")
    remote = ProjectIdentity(experiment_label="my-demo", export_format_version=999)

    with pytest.raises(ProjectMismatch, match="Upgrade PsyNet"):
        confirm_project_identity(local, remote, allow_mismatch=True)


def test_out_of_sync_code_can_be_confirmed_or_overridden():
    local = ProjectIdentity(experiment_label="d", git_commit_sha="a" * 40)
    remote = ProjectIdentity(
        experiment_label="d", git_commit_sha="b" * 40, export_format_version=1
    )

    warnings = []
    confirm_project_identity(
        local, remote, confirm=lambda message: True, emit=warnings.append
    )
    assert any("was launched from Git commit" in message for message in warnings)

    with pytest.raises(ProjectMismatch, match="cancelled"):
        confirm_project_identity(
            local, remote, confirm=lambda message: False, emit=warnings.append
        )

    confirm_project_identity(local, remote, allow_mismatch=True, emit=warnings.append)


def test_out_of_sync_code_fails_without_a_terminal(monkeypatch):
    local = ProjectIdentity(experiment_label="d", git_dirty=True)
    remote = ProjectIdentity(experiment_label="d", export_format_version=1)
    monkeypatch.setattr(
        "sys.stdin", type("NoTty", (), {"isatty": lambda self: False})()
    )

    with pytest.raises(ProjectMismatch, match="allow-project-mismatch"):
        confirm_project_identity(local, remote, emit=lambda message: None)


def test_matching_identity_requires_no_confirmation():
    identity = ProjectIdentity(
        experiment_label="d", git_commit_sha="a" * 40, export_format_version=1
    )

    def refuse(message):
        raise AssertionError("a matching identity must not prompt")

    confirm_project_identity(identity, identity, confirm=refuse, emit=refuse)
