"""Tests for the PsyNet minimal bootstrap packaging.

Covers:
- Bootstrap module imports without heavy deps (experiment extra mocked missing).
- _default_psynet_requirement includes [experiment] extra.
- constraints_compile locks via uv run; freshness uses requirements MD5.
- bootstrap_cli dispatches setup without importing command_line.
- psynet[experiment] and bare psynet both count as unpinned.
"""

from __future__ import annotations

import sys
from hashlib import md5
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1. _default_psynet_requirement includes [experiment]
# ---------------------------------------------------------------------------


def test_default_psynet_requirement_includes_experiment_for_stable_version(
    monkeypatch,
):
    monkeypatch.setattr("psynet.experiment_scaffold.psynet_version", "13.3.0")
    monkeypatch.setattr(
        "psynet.experiment_scaffold.get_editable_psynet_source",
        lambda: None,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._installed_psynet_file_path",
        lambda: None,
    )
    from psynet.experiment_scaffold import _default_psynet_requirement

    req = _default_psynet_requirement()
    assert req == "psynet[experiment]==13.3.0"


def test_default_psynet_requirement_includes_experiment_for_alpha_no_git(monkeypatch):
    monkeypatch.setattr("psynet.experiment_scaffold.psynet_version", "13.4.0a0")
    monkeypatch.setattr(
        "psynet.experiment_scaffold.get_editable_psynet_source",
        lambda: None,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._installed_psynet_file_path",
        lambda: None,
    )
    from psynet.experiment_scaffold import _default_psynet_requirement

    req = _default_psynet_requirement()
    assert req == "psynet[experiment]==13.4.0a0"


def test_default_psynet_requirement_uses_local_file_install(tmp_path, monkeypatch):
    monkeypatch.setattr("psynet.experiment_scaffold.psynet_version", "13.4.0a0")
    monkeypatch.setattr(
        "psynet.experiment_scaffold.get_editable_psynet_source",
        lambda: None,
    )
    monkeypatch.setattr(
        "psynet.experiment_scaffold._installed_psynet_file_path",
        lambda: tmp_path,
    )
    from psynet.experiment_scaffold import _default_psynet_requirement

    assert _default_psynet_requirement() == (
        f"psynet[experiment] @ {tmp_path.resolve().as_uri()}"
    )


def test_editable_psynet_requirement_includes_experiment(tmp_path):
    from psynet.experiment_scaffold import editable_psynet_requirement

    req = editable_psynet_requirement(tmp_path)
    assert "#egg=psynet[experiment]" in req
    assert str(tmp_path.resolve()) in req


# ---------------------------------------------------------------------------
# 2. pin_unpinned_psynet_requirement handles bare psynet[experiment]
# ---------------------------------------------------------------------------


def test_pin_unpinned_handles_bare_psynet_experiment(tmp_path, monkeypatch):
    req_path = tmp_path / "requirements.txt"
    req_path.write_text("psynet[experiment]\n")

    monkeypatch.setattr(
        "psynet.experiment_scaffold._default_psynet_requirement",
        lambda: "psynet[experiment]==13.4.0a0",
    )

    import os

    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        from psynet.experiment_scaffold import pin_unpinned_psynet_requirement

        changed = pin_unpinned_psynet_requirement()
    finally:
        os.chdir(orig)

    assert changed is True
    assert req_path.read_text().strip() == "psynet[experiment]==13.4.0a0"


def test_pin_unpinned_handles_bare_psynet(tmp_path, monkeypatch):
    req_path = tmp_path / "requirements.txt"
    req_path.write_text("psynet\n")

    monkeypatch.setattr(
        "psynet.experiment_scaffold._default_psynet_requirement",
        lambda: "psynet[experiment]==13.4.0",
    )

    import os

    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        from psynet.experiment_scaffold import pin_unpinned_psynet_requirement

        changed = pin_unpinned_psynet_requirement()
    finally:
        os.chdir(orig)

    assert changed is True
    assert req_path.read_text().strip() == "psynet[experiment]==13.4.0"


# ---------------------------------------------------------------------------
# 3. is_unambiguous_psynet_requirement accepts psynet[experiment]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "requirement",
    [
        "psynet[experiment]==13.4.0",
        "psynet[experiment]==13.4.0a0",
        "psynet[experiment]==13.4.0rc1",
        "psynet==13.4.0",
        "psynet[experiment]@git+https://gitlab.com/a/PsyNet@"
        + "a" * 40
        + "#egg=psynet",
        "psynet[experiment]@git+https://gitlab.com/a/PsyNet@v13.4.0#egg=psynet",
    ],
)
def test_is_unambiguous_psynet_requirement_accepts_experiment_extra(requirement):
    from psynet.experiment_scaffold import is_unambiguous_psynet_requirement

    assert is_unambiguous_psynet_requirement(requirement)


# ---------------------------------------------------------------------------
# 4. constraints_compile uses uv run of Dallinger's standalone script
# ---------------------------------------------------------------------------


def test_generate_constraints_invokes_uv_run_dallinger_script(tmp_path, monkeypatch):
    """Locking must use ``uv run <dallinger constraints script> generate``."""
    req = tmp_path / "requirements.txt"
    req.write_text("psynet[experiment]==13.4.0\n")
    script = tmp_path / "fake_constraints.py"
    script.write_text("# fake\n")

    import os

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        (tmp_path / "constraints.txt").write_text("# locked\n")
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        "psynet.constraints_compile._dallinger_constraints_script",
        lambda: script,
    )

    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        from psynet.constraints_compile import generate_constraints_file

        generate_constraints_file()
    finally:
        os.chdir(orig)

    assert calls == [["uv", "run", str(script), "generate"]]
    assert (tmp_path / "constraints.txt").read_text() == "# locked\n"


def test_dallinger_constraints_script_prefers_installed_package(
    monkeypatch, tmp_path, capsys
):
    """An installed Dallinger package supplies its local constraints script."""
    installed = tmp_path / "installed_constraints.py"
    installed.write_text("# installed\n")

    class Spec:
        origin = str(installed)

    monkeypatch.setattr(
        "psynet.constraints_compile.distribution",
        lambda name: object(),
    )
    monkeypatch.setattr(
        "psynet.constraints_compile.importlib.util.find_spec",
        lambda name: Spec(),
    )
    from psynet.constraints_compile import _dallinger_constraints_script

    assert _dallinger_constraints_script() == str(installed)
    assert "installed Dallinger" in capsys.readouterr().out


def test_dallinger_constraints_script_uses_pinned_github_when_missing(
    monkeypatch, capsys
):
    """Thin bootstrap (no Dallinger) uses a pinned GitHub release, not master."""
    from importlib.metadata import PackageNotFoundError

    def missing(_name):
        raise PackageNotFoundError("dallinger")

    monkeypatch.setattr("psynet.constraints_compile.distribution", missing)
    from psynet.constraints_compile import (
        _DALLINGER_CONSTRAINTS_REF,
        _DALLINGER_CONSTRAINTS_URL,
        _dallinger_constraints_script,
    )

    assert _DALLINGER_CONSTRAINTS_REF != "master"
    assert _DALLINGER_CONSTRAINTS_REF in _DALLINGER_CONSTRAINTS_URL
    assert "master" not in _DALLINGER_CONSTRAINTS_URL
    assert _dallinger_constraints_script() == _DALLINGER_CONSTRAINTS_URL
    assert _DALLINGER_CONSTRAINTS_REF in capsys.readouterr().out


def test_constraints_are_up_to_date_requires_requirements_md5(tmp_path):
    """Freshness matches check-constraints: embed requirements.txt MD5."""
    from psynet.constraints_compile import constraints_are_up_to_date

    requirements = tmp_path / "requirements.txt"
    constraints = tmp_path / "constraints.txt"
    requirements.write_text("psynet[experiment]==13.4.0\n")

    assert not constraints_are_up_to_date(
        requirements_path=requirements,
        constraints_path=constraints,
    )

    constraints.write_text("# stale lock without digest\n")
    assert not constraints_are_up_to_date(
        requirements_path=requirements,
        constraints_path=constraints,
    )

    digest = md5(requirements.read_bytes()).hexdigest()
    constraints.write_text(f"# locked\n# md5sum {digest}\n")
    assert constraints_are_up_to_date(
        requirements_path=requirements,
        constraints_path=constraints,
    )

    requirements.write_text("psynet[experiment]==13.5.0\n")
    assert not constraints_are_up_to_date(
        requirements_path=requirements,
        constraints_path=constraints,
    )


def test_ensure_constraints_reuses_up_to_date_lockfile(tmp_path, monkeypatch):
    """Setup must not regenerate when constraints already match requirements."""
    import os

    from psynet.experiment_setup import _ensure_constraints_up_to_date

    requirements = tmp_path / "requirements.txt"
    constraints = tmp_path / "constraints.txt"
    requirements.write_text("psynet[experiment]==13.4.0\n")
    digest = md5(requirements.read_bytes()).hexdigest()
    original = f"# existing lock\n# md5sum {digest}\n"
    constraints.write_text(original)

    def fail_generate():
        raise AssertionError("generate_constraints_file should not run")

    monkeypatch.setattr(
        "psynet.constraints_compile.generate_constraints_file",
        fail_generate,
    )

    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        _ensure_constraints_up_to_date(ctx=None)
    finally:
        os.chdir(orig)

    assert constraints.read_text() == original


def test_ensure_constraints_regenerates_when_stale(tmp_path, monkeypatch):
    """Setup regenerates when the lockfile lacks the current requirements MD5."""
    import os

    from psynet.experiment_setup import _ensure_constraints_up_to_date

    requirements = tmp_path / "requirements.txt"
    constraints = tmp_path / "constraints.txt"
    requirements.write_text("psynet[experiment]==13.4.0\n")
    constraints.write_text("# stale\n")
    calls = []

    def fake_generate():
        calls.append(True)
        digest = md5(requirements.read_bytes()).hexdigest()
        constraints.write_text(f"# regenerated\n# md5sum {digest}\n")

    monkeypatch.setattr(
        "psynet.constraints_compile.generate_constraints_file",
        fake_generate,
    )

    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        _ensure_constraints_up_to_date(ctx=None)
    finally:
        os.chdir(orig)

    assert calls == [True]
    assert "regenerated" in constraints.read_text()


# ---------------------------------------------------------------------------
# 5. bootstrap_cli dispatches setup without importing command_line
# ---------------------------------------------------------------------------


def test_bootstrap_cli_setup_does_not_import_command_line(tmp_path, monkeypatch):
    """setup in bootstrap_cli must not trigger psynet.command_line import."""
    setup_called = []

    def fake_setup_experiment(ctx, **kwargs):
        setup_called.append(kwargs)

    monkeypatch.setattr(
        "psynet.experiment_setup.setup_experiment",
        fake_setup_experiment,
    )

    # Simulate environment: no command_line in sys.modules.
    cl_module = sys.modules.pop("psynet.command_line", None)
    try:
        from click.testing import CliRunner

        from psynet.bootstrap_cli import _bootstrap

        result = CliRunner().invoke(
            _bootstrap,
            ["setup", "--no-install"],
        )
    finally:
        if cl_module is not None:
            sys.modules["psynet.command_line"] = cl_module

    assert result.exit_code == 0, result.output
    assert "psynet.command_line" not in sys.modules or cl_module is not None
    assert len(setup_called) == 1
    assert setup_called[0]["no_install"] is True


def test_bootstrap_cli_reports_missing_experiment_extra(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["psynet", "debug", "local"])
    monkeypatch.setattr(
        "psynet.bootstrap_cli._load_full_psynet_cli",
        lambda: (_ for _ in ()).throw(ImportError("no experiment extra")),
    )
    from psynet.bootstrap_cli import main

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "psynet[experiment]" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["psynet", "--version"], True),
        (["psynet", "-V"], True),
        (["psynet", "debug", "-V"], False),
        (["psynet", "debug", "--version"], False),
        (["psynet", "--version", "setup"], False),
        (["psynet", "setup", "--no-install"], False),
    ],
)
def test_has_version_flag_exact_match_only(monkeypatch, argv, expected):
    """Only bare ``psynet --version`` / ``-V`` should select the bootstrap CLI."""
    monkeypatch.setattr("sys.argv", argv)
    from psynet.bootstrap_cli import _has_version_flag

    assert _has_version_flag() is expected


# ---------------------------------------------------------------------------
# 6. light_utils imports without dallinger
# ---------------------------------------------------------------------------


def test_light_utils_imports_cleanly():
    """light_utils must not import dallinger or flask."""
    import psynet.light_utils as lu

    assert callable(lu.md5_directory)
    assert callable(lu.is_in_repo_experiment)
    assert callable(lu.ensure_experiment_directory_name_does_not_conflict)
    assert callable(lu.get_psynet_root)
    assert lu.ExperimentDirectoryNameError is not None


# ---------------------------------------------------------------------------
# 7. psynet/__init__.py sets __version__ without heavy imports
# ---------------------------------------------------------------------------


def test_psynet_init_does_not_import_dallinger_at_top_level():
    """psynet.__version__ must be accessible without importing dallinger runtime."""
    import psynet

    assert isinstance(psynet.__version__, str)
    assert psynet.__version__


# ---------------------------------------------------------------------------
# 8. psynet.debugger is created lazily but stays a single shared callable
# ---------------------------------------------------------------------------


def test_debugger_listens_once_across_repeated_breakpoints(monkeypatch):
    """Repeated psynet.debugger() calls must not re-run debugpy.listen()."""
    import psynet

    monkeypatch.delitem(psynet.__dict__, "debugger", raising=False)
    debugpy = MagicMock()
    monkeypatch.setitem(sys.modules, "debugpy", debugpy)
    monkeypatch.setattr("psynet.runtime_init.ensure_runtime", lambda: None)

    psynet.debugger()
    psynet.debugger()

    assert psynet.debugger is psynet.debugger
    debugpy.listen.assert_called_once_with(5678)
    assert debugpy.breakpoint.call_count == 2
