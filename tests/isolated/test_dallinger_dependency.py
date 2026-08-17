"""Tests for Dallinger lower-bound resolution from pyproject / metadata."""

from pathlib import Path

import pytest

from psynet.dallinger_dependency import (
    dallinger_constraints_github_ref,
    dallinger_lower_bound_from_pyproject,
    supported_dallinger_lower_bound,
)

ROOT = Path(__file__).resolve().parents[2]


def test_lower_bound_from_pyproject_matches_experiment_extra():
    version = dallinger_lower_bound_from_pyproject(ROOT / "pyproject.toml")
    assert version == "12.2.0"
    assert dallinger_constraints_github_ref() == "v12.2.0"
    assert supported_dallinger_lower_bound() == version


def test_lower_bound_from_pyproject_rejects_missing_dallinger(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["click"]
[project.optional-dependencies]
experiment = ["pandas"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Could not find a Dallinger dependency"):
        dallinger_lower_bound_from_pyproject(pyproject)


def test_lower_bound_parses_pep508_metadata_style(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = []
[project.optional-dependencies]
experiment = ['dallinger[docker] (>=9.1.0,<10) ; python_version >= "3.10"']
""",
        encoding="utf-8",
    )
    assert dallinger_lower_bound_from_pyproject(pyproject) == "9.1.0"


def test_source_pyproject_takes_priority_over_installed_metadata(tmp_path, monkeypatch):
    """Editable source declarations must not be shadowed by stale dist-info."""
    from psynet import dallinger_dependency

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = []
[project.optional-dependencies]
experiment = ["dallinger[docker]>=12.3.0,<13"]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        dallinger_dependency, "_default_pyproject_path", lambda: pyproject
    )
    monkeypatch.setattr(
        dallinger_dependency,
        "_lower_bound_from_installed_metadata",
        lambda: pytest.fail("source checkout should not consult stale metadata"),
    )
    assert supported_dallinger_lower_bound() == "12.3.0"


def test_requirement_match_does_not_accept_similarly_named_distribution(tmp_path):
    """A dallinger-plugin dependency must not masquerade as Dallinger."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["dallinger-plugin>=99.0.0"]
[project.optional-dependencies]
experiment = []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Could not find a Dallinger dependency"):
        dallinger_lower_bound_from_pyproject(pyproject)
