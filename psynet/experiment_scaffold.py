"""Create, update, and prune PsyNet experiment scaffold files."""

import os
import shutil
import stat
from importlib import resources
from pathlib import Path

import click

from psynet.utils import md5_directory
from psynet.version import recommended_python_major_minor

_TEMPLATE_FILES = (
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "README.md",
    "__init__.py",
    "pytest.ini",
    "test.py",
    ".github/workflows/test.yml",
    ".vscode/launch.json",
    "AGENTS.md",
)

_OPTIONAL_TEMPLATE_FILES = ("config.txt",)

_TEMPLATE_DIRECTORIES = ("docker",)

_GENERATED_FILES = {
    "Dockertag": lambda: f"{Path.cwd().name}\n",
    ".python-version": lambda: f"{recommended_python_major_minor}\n",
}

_REMOVABLE_DIRECTORIES = (
    ("docs", "abfc54bbbc3ef9d5948957841727a18b"),
)

_EXECUTABLE_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def scaffold_managed_paths(*, include_optional_files=True) -> frozenset[str]:
    """Return paths managed by the experiment scaffold.

    Parameters
    ----------
    include_optional_files
        Whether to include files that are only created by ``psynet scaffold``,
        rather than by ``psynet update-scripts``.

    Returns
    -------
    frozenset[str]
        Relative paths to scaffold-managed files and directories.
    """
    paths = set(_TEMPLATE_FILES)
    paths.update(_TEMPLATE_DIRECTORIES)
    paths.update(_GENERATED_FILES)
    if include_optional_files:
        paths.update(_OPTIONAL_TEMPLATE_FILES)
    return frozenset(paths)


def _copy_template_file(relative_path, overwrite, treat_empty_file_as_missing=False):
    """Copy one scaffold-managed template file into the experiment directory."""
    destination = Path(relative_path)
    empty_file_needs_template = (
        treat_empty_file_as_missing
        and destination.exists()
        and destination.is_file()
        and destination.stat().st_size == 0
    )
    if destination.exists() and not overwrite and not empty_file_needs_template:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    with resources.as_file(
        resources.files("psynet") / f"resources/experiment_scripts/{relative_path}"
    ) as path:
        shutil.copyfile(path, destination)
    return True


def _write_generated_file(relative_path, contents, overwrite):
    """Write one generated scaffold-managed file into the experiment directory."""
    destination = Path(relative_path)
    if destination.exists() and not overwrite:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contents)
    return True


def _copy_missing_directory_entries(source, destination):
    """Copy missing entries from a template directory without overwriting files."""
    copied = False
    for source_path in source.rglob("*"):
        destination_path = destination / source_path.relative_to(source)
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
        elif not destination_path.exists():
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            copied = True
    return copied


def _remove_empty_parent_dirs(path):
    """Remove now-empty parent directories after deleting scaffold files."""
    workspace_root = Path.cwd()
    while path != workspace_root and path.exists():
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


def _make_docker_entries_executable():
    """Add executable bits to immediate entries in the generated Docker directory."""
    docker_directory = Path("docker")
    if not docker_directory.is_dir():
        return

    for path in docker_directory.iterdir():
        path.chmod(path.stat().st_mode | _EXECUTABLE_BITS)


def scaffold_experiment_directory(
    *,
    overwrite=False,
    include_optional_files=False,
    skip_files=None,
):
    """Create or refresh the standard scaffold-managed experiment files."""
    skip_files = set(skip_files or [])
    action = "Updating" if overwrite else "Scaffolding"
    click.echo(f"{action} PsyNet scripts in ({os.getcwd()})...")

    written = []
    skipped = []

    template_files = list(_TEMPLATE_FILES)
    if include_optional_files:
        template_files.extend(_OPTIONAL_TEMPLATE_FILES)

    for relative_path in template_files:
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        if _copy_template_file(
            relative_path,
            overwrite,
            treat_empty_file_as_missing=relative_path == "config.txt",
        ):
            verb = "updating" if overwrite else "creating"
            click.echo(f"...{verb} {relative_path}.")
            written.append(relative_path)
        else:
            skipped.append(relative_path)

    for relative_path, contents_factory in _GENERATED_FILES.items():
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        if _write_generated_file(relative_path, contents_factory(), overwrite):
            verb = "updating" if overwrite else "creating"
            click.echo(f"...{verb} {relative_path}.")
            written.append(relative_path)
        else:
            skipped.append(relative_path)

    for relative_path in _TEMPLATE_DIRECTORIES:
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        destination = Path(relative_path)
        with resources.as_file(
            resources.files("psynet")
            / f"resources/experiment_scripts/{relative_path}"
        ) as path:
            if destination.exists() and not overwrite:
                if _copy_missing_directory_entries(path, destination):
                    click.echo(
                        f"...filling missing files in {relative_path} directory."
                    )
                    written.append(relative_path)
                else:
                    skipped.append(relative_path)
                continue

            verb = "updating" if overwrite else "creating"
            click.echo(f"...{verb} {relative_path} directory.")
            if overwrite and destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(
                path,
                destination,
                dirs_exist_ok=True,
            )
        written.append(relative_path)

    _make_docker_entries_executable()

    if overwrite:
        # Remove obsolete directories only when they still match the old template.
        for directory, hash_ in _REMOVABLE_DIRECTORIES:
            if Path(directory).exists() and md5_directory(directory) == hash_:
                shutil.rmtree(directory)

    if not overwrite and written:
        click.echo(
            "Scaffolded missing boilerplate files. Use 'psynet update-scripts' to"
            " overwrite existing boilerplate with the latest templates."
        )

    return {"written": written, "skipped": skipped}


def prune_experiment_scaffold(*, preserve_files=None):
    """Remove scaffold-managed files while preserving authored experiment files."""
    preserve_files = set(preserve_files or [])
    managed_paths = scaffold_managed_paths()

    for relative_path in sorted(
        managed_paths - set(_TEMPLATE_DIRECTORIES) - preserve_files
    ):
        path = Path(relative_path)
        if path.exists():
            path.unlink()
            _remove_empty_parent_dirs(path.parent)

    for relative_path in _TEMPLATE_DIRECTORIES:
        if relative_path in preserve_files:
            continue
        path = Path(relative_path)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
