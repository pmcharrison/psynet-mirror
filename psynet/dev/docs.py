"""Build PsyNet's developer documentation from a source checkout."""

import shlex
import shutil
import subprocess
from pathlib import Path

from psynet.utils import get_psynet_root


def make_command(
    target: str = "html",
    *,
    clean: bool = False,
    open_browser: bool = False,
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
        jobs=jobs,
        sphinx_options=sphinx_options,
    )
    command = ["make", target]
    if options:
        command.append(f"SPHINXOPTS={shlex.join(options)}")

    subprocess.run(command, cwd=docs_dir, check=True)

    if open_browser:
        open_html_index(target, build_dir)

    return 0


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
