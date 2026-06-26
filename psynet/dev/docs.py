"""Build PsyNet's developer documentation from a source checkout."""

import shlex
import shutil
import socket
import subprocess
from pathlib import Path

from psynet.utils import get_psynet_root

LIVE_PREVIEW_IGNORE_PATTERNS = ("_build", "_build/*", "_build/**/*")
LIVE_PREVIEW_RE_IGNORE_PATTERNS = (r".*/_build($|/.*)",)


def make_command(
    target: str = "html",
    *,
    clean: bool = False,
    open_browser: bool = False,
    live_preview: bool = False,
    live_preview_port: int = 8000,
    strict: bool = False,
    jobs: str | None = "1",
    sphinx_options: tuple[str, ...] = (),
) -> int:
    """Run the Sphinx Makefile target for PsyNet's documentation."""
    docs_dir = assert_docs_available()
    build_dir = docs_dir / "_build"

    if clean and build_dir.exists():
        shutil.rmtree(build_dir)

    options = build_sphinx_options(
        strict=strict,
        jobs="1" if live_preview else jobs,
        sphinx_options=sphinx_options,
    )
    if live_preview:
        run_live_preview(
            target=target,
            options=options,
            docs_dir=docs_dir,
            build_dir=build_dir,
            port=live_preview_port,
        )
        return 0

    command = ["make", target]
    if options:
        command.append(f"SPHINXOPTS={shlex.join(options)}")

    subprocess.run(command, cwd=docs_dir, check=True)

    if open_browser:
        open_html_index(target, build_dir)

    return 0


def run_live_preview(
    *,
    target: str,
    options: list[str],
    docs_dir: Path,
    build_dir: Path,
    port: int,
) -> None:
    """Serve the HTML docs with automatic rebuilds and browser reloads."""
    if target != "html":
        raise ValueError("--live-preview is only supported for the html docs target.")

    if shutil.which("sphinx-autobuild") is None:
        raise ValueError(
            "sphinx-autobuild is required for --live-preview. "
            "Install or update the PsyNet dev dependencies, for example with "
            "`uv pip install -e '.[dev,slack]'`."
        )

    assert_live_preview_port_available(port)

    command = [
        "sphinx-autobuild",
        *options,
        "--no-color",
        "--open-browser",
        "--port",
        str(port),
    ]
    for pattern in LIVE_PREVIEW_IGNORE_PATTERNS:
        command.extend(["--ignore", pattern])
        command.extend(["--ignore", str(docs_dir / pattern)])
    for pattern in LIVE_PREVIEW_RE_IGNORE_PATTERNS:
        command.extend(["--re-ignore", pattern])

    run_live_preview_process(
        [*command, ".", str(build_dir / "html")],
        docs_dir,
    )


def assert_live_preview_port_available(port: int, host: str = "127.0.0.1") -> None:
    """Fail before building docs if the live-preview server port is occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        is_in_use = sock.connect_ex((host, port)) == 0

    if is_in_use:
        raise ValueError(
            f"Port {port} is already in use. Stop the existing docs preview server "
            f"or choose another port with `--port {port + 1}`."
        )


def run_live_preview_process(
    command: list[str],
    docs_dir: Path,
) -> None:
    """Run sphinx-autobuild."""
    with subprocess.Popen(
        command,
        cwd=docs_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="")

            return_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise

    if return_code:
        raise subprocess.CalledProcessError(return_code, command)


def assert_docs_available() -> Path:
    """Return the docs directory, or fail if not in the source checkout root."""
    root = get_psynet_root().resolve()
    docs_dir = root / "docs"
    if Path.cwd().resolve() != root or not (docs_dir / "Makefile").exists():
        raise ValueError(
            "This command must be run from the PsyNet source checkout root directory "
            "with docs/Makefile present."
        )
    return docs_dir


def build_sphinx_options(
    *,
    strict: bool,
    jobs: str | None,
    sphinx_options: tuple[str, ...],
) -> list[str]:
    """Compose Sphinx options to pass through the docs Makefile."""
    options = list(sphinx_options)
    if strict:
        options.extend(["-W", "--keep-going"])
    if jobs:
        options.extend(["-j", jobs])
    return options


def open_html_index(target: str, build_dir: Path) -> None:
    """Open the built HTML documentation index in the default browser."""
    if target != "html":
        raise ValueError("--open is only supported for the html docs target.")

    open_command = shutil.which("xdg-open") or shutil.which("open")
    if open_command is None:
        raise ValueError("Could not find xdg-open or open to display the HTML docs.")

    subprocess.run(
        [open_command, str(build_dir / "html" / "index.html")],
        check=True,
        stdout=subprocess.DEVNULL,
    )
