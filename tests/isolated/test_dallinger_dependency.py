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
