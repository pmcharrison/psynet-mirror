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


def test_make_command_live_preview_runs_sphinx_autobuild(source_checkout, monkeypatch):
    calls = []

    def fake_run_live_preview_process(command, docs_dir):
        calls.append((command, docs_dir))

    monkeypatch.setattr(
        docs_module,
        "run_live_preview_process",
        fake_run_live_preview_process,
    )
    monkeypatch.setattr(docs_module.shutil, "which", lambda command: command)
    monkeypatch.setattr(
        docs_module,
        "assert_live_preview_port_available",
        lambda port: None,
    )

    with working_directory(source_checkout):
        assert (
            docs_module.make_command(
                live_preview=True,
                live_preview_port=8001,
                strict=True,
                jobs="auto",
                sphinx_options=("--nitpicky",),
            )
            == 0
        )

    assert calls == [
        (
            [
                "sphinx-autobuild",
                "--nitpicky",
                "-W",
                "--keep-going",
                "-j",
                "1",
                "--no-color",
                "--open-browser",
                "--port",
                "8001",
                "--ignore",
                "_build",
                "--ignore",
                str(source_checkout / "docs" / "_build"),
                "--ignore",
                "_build/*",
                "--ignore",
                str(source_checkout / "docs" / "_build" / "*"),
                "--ignore",
                "_build/**/*",
                "--ignore",
                str(source_checkout / "docs" / "_build" / "**" / "*"),
                "--re-ignore",
                r".*/_build($|/.*)",
                ".",
                str(source_checkout / "docs" / "_build" / "html"),
            ],
            source_checkout / "docs",
        )
    ]


def test_live_preview_requires_available_port(monkeypatch):
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def settimeout(self, timeout):
            pass

        def connect_ex(self, address):
            return 0

    monkeypatch.setattr(docs_module.socket, "socket", lambda *args: FakeSocket())

    with pytest.raises(ValueError, match="Port 8000 is already in use"):
        docs_module.assert_live_preview_port_available(8000)


def test_live_preview_process_streams_output(monkeypatch, tmp_path, capsys):
    class FakeProcess:
        stdout = [
            "[sphinx-autobuild] Starting initial build\n",
            "[sphinx-autobuild] Waiting to detect changes...\n",
        ]

        def wait(self):
            return 0

        def terminate(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_popen(command, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(docs_module.subprocess, "Popen", fake_popen)

    docs_module.run_live_preview_process(
        ["sphinx-autobuild"],
        tmp_path,
    )

    assert "Starting initial build" in capsys.readouterr().out


def test_live_preview_requires_sphinx_autobuild(source_checkout, monkeypatch):
    monkeypatch.setattr(docs_module.shutil, "which", lambda command: None)

    with working_directory(source_checkout):
        with pytest.raises(ValueError, match="sphinx-autobuild is required"):
            docs_module.make_command(live_preview=True)


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


def test_live_preview_requires_html_target(source_checkout, monkeypatch):
    monkeypatch.setattr(
        docs_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    with working_directory(source_checkout):
        with pytest.raises(ValueError, match="only supported for the html docs target"):
            docs_module.make_command(target="dirhtml", live_preview=True)
