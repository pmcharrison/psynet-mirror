"""Tests for PsyNet requirement pinning helpers."""

from pathlib import Path

import pytest

from psynet.experiment_scaffold import (
    _default_psynet_requirement,
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
            "https://gitlab.com/PsyNetDev/PsyNet.git/",
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
            "git@gitlab.com:alice/PsyNet.git/",
            "git+https://gitlab.com/alice/PsyNet",
        ),
        (
            "ssh://git@gitlab.com/alice/PsyNet.git",
            "git+https://gitlab.com/alice/PsyNet",
        ),
        (
            "ssh://git@gitlab.com/alice/PsyNet.git/",
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
        (
            "ssh://git@git.example.com/alice/PsyNet.git/",
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
        f"psynet[experiment]@git+https://gitlab.com/alice/PsyNet@{commit}#egg=psynet"
    )


def test_commit_psynet_requirement_strips_trailing_slash_from_origin(
    tmp_path, monkeypatch
):
    from psynet.experiment_scaffold import is_unambiguous_psynet_requirement

    source = tmp_path / "psynet"
    source.mkdir()
    commit = "b" * 40
    monkeypatch.setattr(
        "psynet.experiment_scaffold._current_source_commit",
        lambda _source=None: commit,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._git_remote_url",
        lambda _source, remote="origin": "ssh://git@gitlab.com/alice/PsyNet.git/",
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._remote_tracking_refs_contain_commit",
        lambda _source, _commit, remote="origin": True,
    )

    requirement = commit_psynet_requirement(source)
    assert requirement == (
        f"psynet[experiment]@git+https://gitlab.com/alice/PsyNet@{commit}#egg=psynet"
    )
    assert is_unambiguous_psynet_requirement(requirement)


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


def test_default_psynet_requirement_propagates_commit_pin_errors(monkeypatch):
    """Alpha pins must not invent a PsyNetDev URL when commit pinning fails."""
    commit = "e" * 40
    source = Path("/tmp/fake-psynet-editable")
    monkeypatch.setattr("psynet.experiment_scaffold.psynet_version", "13.4.0a0")
    monkeypatch.setattr(
        "psynet.experiment_scaffold.get_editable_psynet_source",
        lambda: source,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._current_source_commit",
        lambda _source=None: commit,
    )

    def _fail(_source: Path) -> str:
        raise ValueError(
            f"Commit {commit[:12]} is not available on git remote 'origin' "
            "(https://gitlab.com/alice/PsyNet.git). Push your PsyNet commits first "
            "(`git push origin HEAD`), then retry, or use "
            "--psynet-source editable."
        )

    monkeypatch.setattr(
        "psynet.experiment_scaffold.commit_psynet_requirement",
        _fail,
    )

    with pytest.raises(ValueError, match="not available on git remote 'origin'"):
        _default_psynet_requirement()


def test_default_psynet_requirement_uses_origin_commit_pin(monkeypatch):
    commit = "f" * 40
    source = Path("/tmp/fake-psynet-editable")
    monkeypatch.setattr("psynet.experiment_scaffold.psynet_version", "13.4.0a0")
    monkeypatch.setattr(
        "psynet.experiment_scaffold.get_editable_psynet_source",
        lambda: source,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._current_source_commit",
        lambda _source=None: commit,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold.commit_psynet_requirement",
        lambda _source: (
            f"psynet[experiment]@git+https://gitlab.com/alice/PsyNet@{commit}#egg=psynet"
        ),
    )

    assert _default_psynet_requirement() == (
        f"psynet[experiment]@git+https://gitlab.com/alice/PsyNet@{commit}#egg=psynet"
    )


def test_default_psynet_requirement_falls_back_to_version_without_git(monkeypatch):
    monkeypatch.setattr("psynet.experiment_scaffold.psynet_version", "13.4.0a0")
    monkeypatch.setattr(
        "psynet.experiment_scaffold.get_editable_psynet_source",
        lambda: None,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._installed_psynet_file_path",
        lambda: None,
    )

    assert _default_psynet_requirement() == "psynet[experiment]==13.4.0a0"
