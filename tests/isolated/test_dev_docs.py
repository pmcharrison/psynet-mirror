import subprocess

import pytest

from psynet.dev import docs as docs_module
from psynet.utils import working_directory


@pytest.fixture
def source_checkout(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "Makefile").write_text("html:\n", encoding="utf-8")
    monkeypatch.setattr(docs_module, "get_psynet_root", lambda: tmp_path)
    return tmp_path


def test_make_command_runs_docs_make_target_with_options(source_checkout, monkeypatch):
    build_dir = source_checkout / "docs" / "_build"
    build_dir.mkdir()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(docs_module.subprocess, "run", fake_run)

    with working_directory(source_checkout):
        assert (
            docs_module.make_command(
                target="dirhtml",
                clean=True,
                strict=True,
                jobs="auto",
                sphinx_options=("--nitpicky",),
            )
            == 0
        )

    assert not build_dir.exists()
    assert calls == [
        (
            [
                "make",
                "dirhtml",
                "SPHINXOPTS=--nitpicky -W --keep-going -j auto",
            ],
            {
                "cwd": source_checkout / "docs",
                "check": True,
            },
        )
    ]


def test_make_command_defaults_to_html_with_serial_jobs(source_checkout, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(docs_module.subprocess, "run", fake_run)

    with working_directory(source_checkout):
        assert docs_module.make_command() == 0

    assert calls == [
        (
            ["make", "html", "SPHINXOPTS=-j 1"],
            {
                "cwd": source_checkout / "docs",
                "check": True,
            },
        )
    ]


def test_make_command_requires_source_checkout_root(source_checkout, tmp_path):
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()

    with working_directory(other_dir):
        with pytest.raises(ValueError, match="source checkout root"):
            docs_module.make_command()


def test_open_requires_html_target(source_checkout, monkeypatch):
    monkeypatch.setattr(
        docs_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    with working_directory(source_checkout):
        with pytest.raises(ValueError, match="only supported for the html docs target"):
            docs_module.make_command(target="dirhtml", open_browser=True)
