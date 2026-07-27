"""Tests for PsyNet requirement pinning helpers."""

import pytest

from psynet.experiment_scaffold import (
    _normalize_git_remote_to_pip_base,
    commit_psynet_requirement,
)


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        (
            "https://gitlab.com/PsyNetDev/PsyNet.git",
            "git+https://gitlab.com/PsyNetDev/PsyNet",
        ),
        (
            "https://gitlab.com/alice/PsyNet.git",
            "git+https://gitlab.com/alice/PsyNet",
        ),
        (
            "git@gitlab.com:alice/PsyNet.git",
            "git+https://gitlab.com/alice/PsyNet",
        ),
        (
            "ssh://git@gitlab.com/alice/PsyNet.git",
            "git+https://gitlab.com/alice/PsyNet",
        ),
        (
            "git@github.com:alice/PsyNet.git",
            "git+https://github.com/alice/PsyNet",
        ),
        (
            "git@git.example.com:alice/PsyNet.git",
            "git+ssh://git@git.example.com/alice/PsyNet",
        ),
        (
            "ssh://git@git.example.com/alice/PsyNet.git",
            "git+ssh://git@git.example.com/alice/PsyNet",
        ),
    ],
)
def test_normalize_git_remote_to_pip_base(remote, expected):
    assert _normalize_git_remote_to_pip_base(remote) == expected


def test_normalize_git_remote_rejects_unknown_urls():
    with pytest.raises(ValueError, match="Unrecognized git remote URL"):
        _normalize_git_remote_to_pip_base("not-a-remote")


def test_commit_psynet_requirement_uses_origin_remote(tmp_path, monkeypatch):
    source = tmp_path / "psynet"
    source.mkdir()
    commit = "b" * 40
    monkeypatch.setattr(
        "psynet.experiment_scaffold._current_source_commit",
        lambda _source=None: commit,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._git_remote_url",
        lambda _source, remote="origin": "git@gitlab.com:alice/PsyNet.git",
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._remote_tracking_refs_contain_commit",
        lambda _source, _commit, remote="origin": True,
    )

    assert commit_psynet_requirement(source) == (
        f"psynet@git+https://gitlab.com/alice/PsyNet@{commit}#egg=psynet"
    )


def test_commit_psynet_requirement_requires_pushed_commit(tmp_path, monkeypatch):
    source = tmp_path / "psynet"
    source.mkdir()
    commit = "c" * 40
    monkeypatch.setattr(
        "psynet.experiment_scaffold._current_source_commit",
        lambda _source=None: commit,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._git_remote_url",
        lambda _source, remote="origin": "https://gitlab.com/alice/PsyNet.git",
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._remote_tracking_refs_contain_commit",
        lambda _source, _commit, remote="origin": False,
    )

    with pytest.raises(ValueError, match="not available on git remote 'origin'"):
        commit_psynet_requirement(source)


def test_commit_psynet_requirement_requires_origin_remote(tmp_path, monkeypatch):
    source = tmp_path / "psynet"
    source.mkdir()
    monkeypatch.setattr(
        "psynet.experiment_scaffold._current_source_commit",
        lambda _source=None: "d" * 40,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._git_remote_url",
        lambda _source, remote="origin": None,
    )

    with pytest.raises(ValueError, match="Could not determine git remote 'origin'"):
        commit_psynet_requirement(source)
