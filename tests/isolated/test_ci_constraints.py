import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
DALLINGER_CONSTRAINTS = ROOT / "ci" / "dallinger-dev-requirements.txt"


def test_vendored_dallinger_constraints_match_pyproject_dependency():
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dallinger_dependency = next(
        dependency
        for dependency in pyproject["project"]["dependencies"]
        if dependency.startswith("dallinger[")
    )
    dependency_version = re.search(r">=(\d+\.\d+\.\d+)", dallinger_dependency).group(1)

    constraints = DALLINGER_CONSTRAINTS.read_text(encoding="utf-8")
    snapshot_version = re.search(
        r"^# PsyNet CI snapshot for Dallinger release: v(\d+\.\d+\.\d+)$",
        constraints,
        flags=re.MULTILINE,
    ).group(1)
    source_version = re.search(
        r"^# Source: https://raw\.githubusercontent\.com/Dallinger/Dallinger/v(\d+\.\d+\.\d+)/dev-requirements\.txt$",
        constraints,
        flags=re.MULTILINE,
    ).group(1)

    assert snapshot_version == dependency_version
    assert source_version == dependency_version
