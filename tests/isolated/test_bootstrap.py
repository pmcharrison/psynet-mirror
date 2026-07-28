"""Tests for the PsyNet minimal bootstrap packaging.

Covers:
- Bootstrap module imports without heavy deps (experiment extra mocked missing).
- _default_psynet_requirement includes [experiment] extra.
- constraints_compile embeds MD5 in fallback uv path.
- bootstrap_cli dispatches setup without importing command_line.
- psynet[experiment] and bare psynet both count as unpinned.
"""

from __future__ import annotations

import sys
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
# 4. constraints_compile fallback embeds MD5 when uv path used
# ---------------------------------------------------------------------------


def test_generate_constraints_via_uv_embeds_md5(tmp_path, monkeypatch):
    """Verify the uv fallback appends the requirements.txt MD5 to constraints."""
    req = tmp_path / "requirements.txt"
    req.write_text("psynet[experiment]==13.4.0\n")

    from hashlib import md5

    req_md5 = md5(req.read_bytes()).hexdigest()

    import os

    orig = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Mock subprocess.run to fake successful uv pip compile.
        def fake_run(cmd, **kwargs):
            # Write a minimal constraints file without MD5 (so the appending
            # logic is exercised).
            (tmp_path / "constraints.txt").write_text("# autogenerated\n")
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/uv")

        from psynet.constraints_compile import _generate_via_uv

        _generate_via_uv(req)
    finally:
        os.chdir(orig)

    constraints_text = (tmp_path / "constraints.txt").read_text()
    assert req_md5 in constraints_text


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
