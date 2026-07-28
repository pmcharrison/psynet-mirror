"""Create, update, and prune PsyNet experiment scaffold files."""

import json
import re
import shutil
import stat
import subprocess
import sys
from importlib import metadata, resources
from pathlib import Path
from urllib.parse import unquote, urlparse

import click

from psynet.light_utils import md5_directory
from psynet.version import psynet_version

_TEMPLATE_FILES = (
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "README.md",
    "__init__.py",
    "pytest.ini",
    "test.py",
    "config.txt",
    ".github/workflows/test.yml",
    ".vscode/launch.json",
    "AGENTS.md",
)

# Create these when missing, but never overwrite existing copies (authors customize them).
_PRESERVE_EXISTING_TEMPLATE_FILES = frozenset({"config.txt", "README.md"})

_TEMPLATE_DIRECTORIES = ("docker",)

# Minimal scaffold subset needed to run locally (debug/test). Omits IDE/CI-only
# templates such as ``.vscode/`` and ``.github/workflows/``.
_TEMPLATE_FILES_REQUIRED_FOR_LOCAL_RUN = (
    ".gitignore",
    "Dockerfile",
    "test.py",
    "config.txt",
)

_GENERATED_FILES = {
    "Dockertag": lambda: dockertag_contents(),
    ".python-version": lambda: f"{_current_python_major_minor()}\n",
}

_REMOVABLE_DIRECTORIES = (("docs", "abfc54bbbc3ef9d5948957841727a18b"),)

_EMPTY_RESOURCE_DIRECTORIES = ("static", "templates")

_EXECUTABLE_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

_BOOTSTRAP_FILES = ("experiment.py", "requirements.txt")

_EXPERIMENT_PY_TEMPLATE = """\
import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = {label!r}

    timeline = Timeline(
        InfoPage("Welcome!", time_estimate=5),
    )
"""

_REQUIREMENTS_TXT_COMMENTS = """\

# Alternatively, you can use one of the following syntaxes to specify a custom PsyNet version
# psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.4.0#egg=psynet
# psynet@git+https://gitlab.com/PsyNetDev/PsyNet@45f317688af59350f9a6f3052fd73076318f2775#egg=psynet
# psynet@git+https://gitlab.com/PsyNetDev/PsyNet@45f31768#egg=psynet
"""


def _current_python_major_minor() -> str:
    """Return the running interpreter's major and minor version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def dockertag_contents() -> str:
    """Return Dockertag file contents for the current experiment directory."""
    return f"{Path.cwd().name}\n"


def _experiment_script_resource(relative_path: str):
    """Return a Traversable for a packaged experiment-script template path."""
    return resources.files("psynet") / f"resources/experiment_scripts/{relative_path}"


def scaffold_managed_paths() -> frozenset[str]:
    """Return paths managed by the experiment scaffold.

    Returns
    -------
    frozenset[str]
        Relative paths to scaffold-managed files and directories.
    """
    paths = set(_TEMPLATE_FILES)
    paths.update(_TEMPLATE_DIRECTORIES)
    paths.update(_GENERATED_FILES)
    return frozenset(paths)


def scaffold_paths_required_for_local_run() -> frozenset[str]:
    """Return scaffold paths required before running an experiment locally.

    This is a deliberate subset of :func:`scaffold_managed_paths`, covering the
    files and directories needed for local runs rather than optional IDE/CI
    templates.
    """
    required = set(_TEMPLATE_FILES_REQUIRED_FOR_LOCAL_RUN) | set(_TEMPLATE_DIRECTORIES)
    managed = scaffold_managed_paths()
    unexpected = required - managed
    if unexpected:
        raise RuntimeError(
            "Required local-run scaffold paths must be scaffold-managed: "
            + ", ".join(sorted(unexpected))
        )
    return frozenset(required)


def missing_scaffold_paths_required_for_local_run(
    root: Path | str | None = None,
) -> list[str]:
    """Return required local-run scaffold paths missing from ``root``.

    Directory members of the required set must exist as directories; other members
    must exist as filesystem paths.
    """
    base = Path(".") if root is None else Path(root)
    directory_names = set(_TEMPLATE_DIRECTORIES)
    missing = []
    for relative_path in sorted(scaffold_paths_required_for_local_run()):
        path = base / relative_path
        if relative_path in directory_names:
            present = path.is_dir()
        else:
            present = path.exists()
        if not present:
            missing.append(relative_path)
    return missing


def _default_experiment_label() -> str:
    """Build a readable experiment label from the current directory name."""
    return Path.cwd().name.replace("_", " ").replace("-", " ").strip() or "Experiment"


def _default_experiment_py() -> str:
    """Return a minimal starter ``experiment.py``."""
    return _EXPERIMENT_PY_TEMPLATE.format(label=_default_experiment_label())


def _default_requirements_txt() -> str:
    """Return a starter ``requirements.txt`` for the current PsyNet version."""
    requirement = _default_psynet_requirement()
    return f"{requirement}\n{_REQUIREMENTS_TXT_COMMENTS}"


_PUBLIC_HTTPS_GIT_HOSTS = frozenset({"gitlab.com", "github.com", "www.github.com"})


def _normalize_git_repo_path(path: str) -> str:
    """Strip trailing slashes and an optional ``.git`` suffix from a repo path."""
    return path.rstrip("/").removesuffix(".git")


def _normalize_git_remote_to_pip_base(remote_url: str) -> str:
    """Convert a git remote URL into a pip ``git+…`` base without a ref.

    SSH remotes on public hosts (GitLab/GitHub) are normalized to HTTPS for
    more portable requirement pins. Other SSH remotes keep ``git+ssh``.
    """
    remote_url = remote_url.strip()
    scp_match = re.match(r"^git@([^:]+):(.+)$", remote_url)
    if scp_match:
        host, path = scp_match.groups()
        path = _normalize_git_repo_path(path).lstrip("/")
        if host in _PUBLIC_HTTPS_GIT_HOSTS:
            return f"git+https://{host}/{path}"
        return f"git+ssh://git@{host}/{path}"

    if remote_url.startswith("git+"):
        remote_url = remote_url[4:]

    parsed = urlparse(remote_url)
    if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.path:
        path = _normalize_git_repo_path(parsed.path)
        return f"git+{parsed.scheme}://{parsed.hostname}{path}"

    if parsed.scheme == "ssh" and parsed.hostname and parsed.path:
        path = _normalize_git_repo_path(parsed.path).lstrip("/")
        if parsed.hostname in _PUBLIC_HTTPS_GIT_HOSTS:
            return f"git+https://{parsed.hostname}/{path}"
        return f"git+ssh://git@{parsed.hostname}/{path}"

    raise ValueError(f"Unrecognized git remote URL: {remote_url}")


def _git_remote_url(source: Path, remote: str = "origin") -> str | None:
    """Return the configured URL for a git remote, if present."""
    try:
        url = subprocess.check_output(
            ["git", "-C", str(source), "remote", "get-url", remote],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return url or None


def _remote_tracking_refs_contain_commit(
    source: Path, commit: str, remote: str = "origin"
) -> bool:
    """Return whether a local remote-tracking ref already contains ``commit``."""
    try:
        output = subprocess.check_output(
            ["git", "-C", str(source), "branch", "-r", "--contains", commit],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    prefix = f"{remote}/"
    return any(line.strip().startswith(prefix) for line in output.splitlines())


def _remote_advertises_commit(
    source: Path, commit: str, remote: str = "origin"
) -> bool:
    """Return whether ``remote`` can serve ``commit``.

    Uses ``git fetch --dry-run`` so CI merge-request checkouts still work when
    they lack ``origin/<branch>`` remote-tracking refs for ``git branch -r
    --contains``. Looking up the SHA with ``git ls-remote <remote> <sha>`` is
    not reliable on GitLab.
    """
    try:
        subprocess.check_call(
            ["git", "-C", str(source), "fetch", "--dry-run", remote, commit],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _remote_contains_commit(source: Path, commit: str, remote: str = "origin") -> bool:
    """Return whether ``commit`` is available on ``remote``.

    Prefers local remote-tracking refs, then falls back to asking the remote
    whether it can serve ``commit``.
    """
    return _remote_tracking_refs_contain_commit(
        source, commit, remote=remote
    ) or _remote_advertises_commit(source, commit, remote=remote)


def _installed_psynet_file_path() -> Path | None:
    """Return the local path when PsyNet was installed from a ``file://`` URL.

    Covers both editable and non-editable path installs (for example
    ``uv pip install /path/to/PsyNet`` or ``uv pip install -e /path/to/PsyNet``).
    """
    try:
        direct_url = metadata.distribution("psynet").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    if direct_url is None:
        return None
    installation = json.loads(direct_url)
    parsed_url = urlparse(installation["url"])
    if parsed_url.scheme != "file":
        return None
    return Path(unquote(parsed_url.path)).resolve()


def _default_psynet_requirement() -> str:
    """Return a resolvable PsyNet requirement for a new experiment.

    Always includes the ``[experiment]`` extra so that ``psynet setup`` installs
    the full runtime.

    Resolution order:

    1. Editable checkout → commit pin (alphas, when pushed) or editable path.
    2. Non-editable local path install → ``psynet[experiment] @ file://...``.
    3. Otherwise → version pin ``psynet[experiment]==<version>``.
    """
    editable_source = get_editable_psynet_source()
    if editable_source is not None:
        if re.search(r"a\d+$", psynet_version):
            if _current_source_commit(editable_source) is not None:
                return commit_psynet_requirement(editable_source)
        return editable_psynet_requirement(editable_source)

    local_path = _installed_psynet_file_path()
    if local_path is not None:
        return f"psynet[experiment] @ {local_path.as_uri()}"

    return f"psynet[experiment]=={psynet_version}"


def get_editable_psynet_source() -> Path | None:
    """Return the source path when PsyNet is installed in editable mode."""
    try:
        direct_url = metadata.distribution("psynet").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    if direct_url is None:
        return None

    installation = json.loads(direct_url)
    if not installation.get("dir_info", {}).get("editable", False):
        return None
    parsed_url = urlparse(installation["url"])
    if parsed_url.scheme != "file":
        return None
    return Path(unquote(parsed_url.path)).resolve()


def editable_psynet_requirement(source: Path) -> str:
    """Return a named editable requirement for a local PsyNet checkout.

    The ``[experiment]`` extra is included so that a standalone experiment's
    environment gets the full runtime even when PsyNet is installed editable.
    """
    return f"-e {source.resolve().as_uri()}#egg=psynet[experiment]"


def commit_psynet_requirement(source: Path) -> str:
    """Return a portable requirement for a PsyNet checkout's current commit.

    The pin uses the checkout's ``origin`` remote so forks work. The commit must
    already be reachable from a remote-tracking ref (typically after
    ``git push``).
    """
    source = Path(source)
    commit = _current_source_commit(source)
    if commit is None:
        raise ValueError(f"Could not determine a Git commit for {source}.")

    remote_url = _git_remote_url(source, remote="origin")
    if remote_url is None:
        raise ValueError(
            f"Could not determine git remote 'origin' for {source}. "
            "Add an origin remote, or use --psynet-source editable."
        )

    try:
        pip_base = _normalize_git_remote_to_pip_base(remote_url)
    except ValueError as exc:
        raise ValueError(
            f"Could not convert git remote 'origin' ({remote_url}) into a pip "
            "requirement. Use --psynet-source editable, or set origin to an "
            "https/ssh git URL."
        ) from exc

    if not _remote_contains_commit(source, commit, remote="origin"):
        raise ValueError(
            f"Commit {commit[:12]} is not available on git remote 'origin' "
            f"({remote_url}). Push your PsyNet commits first "
            "(`git push origin HEAD`), then retry, or use "
            "--psynet-source editable."
        )

    return f"psynet[experiment]@{pip_base}@{commit}#egg=psynet"


def _is_psynet_requirement_line(line: str) -> bool:
    """Return whether a requirements.txt line is a PsyNet dependency entry.

    Matches bare ``psynet``, ``psynet[experiment]``, and git-URL forms with
    ``#egg=psynet`` or ``#egg=psynet[experiment]``.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return bool(
        re.match(r"(?i)^psynet(?:\s*$|\s*[@<>=!~\[])", stripped)
        or re.search(r"(?i)#egg=psynet(?:\[[\w,]+\])?(?:\s|$)", stripped)
    )


def is_unambiguous_psynet_requirement(requirement: str) -> bool:
    """Return whether a PsyNet requirement pins a version or commit.

    Accepted formats are (with or without the ``[experiment]`` extra):

    - ``psynet[experiment]==<version>`` / ``psynet==<version>``
    - ``psynet[experiment]@git+https://<host>/<path>@v<version>#egg=psynet``
    - ``psynet[experiment]@git+https://<host>/<path>@<commit-hash>#egg=psynet``
    - ``psynet[experiment]@git+ssh://git@<host>/<path>@<commit-hash>#egg=psynet``
    """
    commit_or_tag = (
        r"(?:[a-fA-F0-9]{8,40}|v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
        r"(?:(?:rc|a)\d+)?)"
    )
    git_path = r"[\w.+\-]+(?:/[\w.+\-]+)+"
    extras = r"(?:\[[\w,\s]+\])?"
    egg = r"(?:#egg=psynet(?:\[[\w,]+\])?)?"
    patterns = [
        rf"^psynet{extras}(\s?)@(\s?)git\+https://[\w.-]+/{git_path}(\.git)?@"
        rf"{commit_or_tag}{egg}$",
        rf"^psynet{extras}(\s?)@(\s?)git\+ssh://git@[\w.-]+/{git_path}(\.git)?@"
        rf"{commit_or_tag}{egg}$",
        rf"^psynet{extras}(\s?)==(\s?)\d+\.\d+\.\d+((rc|a)\d+)?$",
    ]
    return any(re.fullmatch(pattern, requirement.strip()) for pattern in patterns)


def get_psynet_requirement() -> str | None:
    """Return the active PsyNet entry from requirements.txt."""
    matches = [
        line.strip()
        for line in Path("requirements.txt").read_text().splitlines()
        if _is_psynet_requirement_line(line)
    ]
    if len(matches) > 1:
        raise ValueError("requirements.txt contains multiple PsyNet requirements.")
    return matches[0] if matches else None


def set_psynet_requirement(requirement: str) -> bool:
    """Replace or add the active PsyNet entry in requirements.txt."""
    path = Path("requirements.txt")
    lines = path.read_text().splitlines(keepends=True)
    existing = get_psynet_requirement()
    if existing == requirement:
        return False

    replaced = False
    updated_lines = []
    for line in lines:
        if line.strip() == existing:
            newline = "\n" if line.endswith("\n") else ""
            updated_lines.append(f"{requirement}{newline}")
            replaced = True
        else:
            updated_lines.append(line)
    if not replaced:
        updated_lines.insert(0, f"{requirement}\n")
    path.write_text("".join(updated_lines))
    return True


def pin_unpinned_psynet_requirement() -> bool:
    """Pin a bare PsyNet requirement to the active version or source commit.

    Both ``psynet`` and ``psynet[experiment]`` (case-insensitive) are treated
    as unpinned and will be replaced with the result of
    :func:`_default_psynet_requirement`.
    """
    requirement = get_psynet_requirement()
    if requirement is None:
        return False
    bare = re.sub(r"\[.*\]", "", requirement).strip().lower()
    if bare != "psynet":
        return False
    return set_psynet_requirement(_default_psynet_requirement())


def _current_source_commit(source=None) -> str | None:
    """Return the source checkout commit when PsyNet is installed from Git."""
    source = Path(__file__).parent.parent if source is None else Path(source)
    try:
        commit = subprocess.check_output(
            [
                "git",
                "-C",
                str(source),
                "rev-parse",
                "HEAD",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None


def _bootstrap_authored_files(skip_files):
    """Create missing starter experiment files without overwriting existing ones.

    Contents are computed before any writes so a failed PsyNet pin (for example
    an unpushed alpha commit) does not leave a partial authored bootstrap.
    """
    written = []
    skipped = []
    bootstrap_files = {
        "experiment.py": _default_experiment_py,
        "requirements.txt": _default_requirements_txt,
    }

    pending = []
    for relative_path, contents_factory in bootstrap_files.items():
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        # Authored starter files are never overwritten, even during scripts update.
        if Path(relative_path).exists():
            skipped.append(relative_path)
            continue

        pending.append((relative_path, contents_factory()))

    for relative_path, contents in pending:
        if _write_generated_file(relative_path, contents, overwrite=False):
            written.append(relative_path)
        else:
            skipped.append(relative_path)

    return written, skipped


def _summarize_written_paths(written):
    """Build a short human summary of created or updated paths."""
    authored = [path for path in written if path in _BOOTSTRAP_FILES]
    boilerplate_count = sum(1 for path in written if path not in _BOOTSTRAP_FILES)

    if authored and boilerplate_count:
        authored_text = ", ".join(authored)
        noun = "boilerplate file" if boilerplate_count == 1 else "boilerplate files"
        return f"{authored_text}, and {boilerplate_count} {noun}"
    if authored:
        return ", ".join(authored)
    if boilerplate_count:
        noun = "boilerplate file" if boilerplate_count == 1 else "boilerplate files"
        return f"{boilerplate_count} {noun}"
    return None


def _report_scaffold_result(written, *, overwrite):
    """Print a concise summary of a scaffold or update run."""
    directory_name = Path.cwd().name
    summary = _summarize_written_paths(written)

    if overwrite:
        if summary:
            click.echo(f"Updated experiment scripts in {directory_name}")
            click.echo(f"  updated: {summary}")
        else:
            click.echo(
                f"Experiment scripts in {directory_name} are already up to date."
            )
        return

    if summary:
        click.echo(f"Scaffolded experiment in {directory_name}")
        click.echo(f"  created: {summary}")
        return

    click.echo("Nothing to scaffold; experiment boilerplate is already present.")


def _copy_template_file(relative_path, overwrite):
    """Copy one scaffold-managed template file into the experiment directory."""
    destination = Path(relative_path)
    if relative_path in _PRESERVE_EXISTING_TEMPLATE_FILES:
        overwrite = False
    if destination.exists() and not overwrite:
        return False
    if overwrite and _template_file_matches(relative_path):
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    with resources.as_file(_experiment_script_resource(relative_path)) as path:
        shutil.copyfile(path, destination)
    return True


def _assert_managed_path_is_safe(relative_path):
    """Reject managed paths containing symlink components."""
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise click.UsageError(
            f"Refusing to manage unsafe scaffold path '{relative_path}'."
        )

    current = Path()
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise click.UsageError(
                f"Refusing to manage '{relative_path}' because '{current}' "
                "is a symlink."
            )


def _assert_scaffold_paths_are_safe(paths):
    """Validate scaffold destinations before making any changes."""
    paths = set(paths)
    for relative_path in paths:
        _assert_managed_path_is_safe(relative_path)

    for relative_path in _TEMPLATE_DIRECTORIES:
        if relative_path not in paths:
            continue
        directory = Path(relative_path)
        if directory.is_dir():
            for path in directory.rglob("*"):
                if path.is_symlink():
                    raise click.UsageError(
                        f"Refusing to manage '{relative_path}' because '{path}' "
                        "is a symlink."
                    )


def _template_file_matches(relative_path):
    """Return whether an existing file matches its scaffold template."""
    destination = Path(relative_path)
    if not destination.is_file():
        return False

    with resources.as_file(_experiment_script_resource(relative_path)) as template:
        return destination.read_bytes() == template.read_bytes()


def _generated_file_matches(relative_path):
    """Return whether an existing generated file has its expected contents."""
    destination = Path(relative_path)
    return (
        destination.is_file()
        and destination.read_text() == _GENERATED_FILES[relative_path]()
    )


def _template_directory_matches(relative_path):
    """Return whether an existing directory matches its scaffold template."""
    destination = Path(relative_path)
    if not destination.is_dir():
        return False
    with resources.as_file(_experiment_script_resource(relative_path)) as template:
        return md5_directory(destination) == md5_directory(template)


def _managed_path_matches_scaffold(relative_path):
    """Return whether a managed path still has its generated contents."""
    if relative_path in _TEMPLATE_FILES:
        return _template_file_matches(relative_path)
    if relative_path in _GENERATED_FILES:
        return _generated_file_matches(relative_path)
    if relative_path in _TEMPLATE_DIRECTORIES:
        return _template_directory_matches(relative_path)
    raise ValueError(f"Unknown scaffold-managed path: {relative_path}")


def _write_generated_file(relative_path, contents, overwrite):
    """Write one generated scaffold-managed file into the experiment directory."""
    destination = Path(relative_path)
    if destination.exists():
        if not overwrite:
            return False
        if destination.is_file() and destination.read_bytes() == contents.encode():
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
    workspace_root = Path.cwd().resolve()
    path = path.resolve()
    while path != workspace_root and path.exists():
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


def _remove_empty_resource_directories():
    """Remove resource directories that contain no authored files."""
    for relative_path in _EMPTY_RESOURCE_DIRECTORIES:
        path = Path(relative_path)
        if not path.is_dir() or path.is_symlink():
            continue

        entries = list(path.iterdir())
        if relative_path == "static":
            disposable = all(
                entry.name == "assets" and entry.is_symlink() for entry in entries
            )
        else:
            disposable = all(
                entry.name == ".keep" and entry.is_file() and not entry.is_symlink()
                for entry in entries
            )
        if not disposable:
            continue

        for entry in entries:
            entry.unlink()
        path.rmdir()


def _make_docker_entries_executable():
    """Add executable bits to immediate entries in the generated Docker directory."""
    docker_directory = Path("docker")
    if not docker_directory.is_dir():
        return False

    changed = False
    for path in docker_directory.iterdir():
        current_mode = path.stat().st_mode
        updated_mode = current_mode | _EXECUTABLE_BITS
        if updated_mode != current_mode:
            path.chmod(updated_mode)
            changed = True
    return changed


def scaffold_experiment_directory(
    *,
    overwrite=False,
    skip_files=None,
):
    """Create or refresh the standard scaffold-managed experiment files.

    ``config.txt`` is part of the default scaffold and is created when missing,
    but existing copies are never overwritten (authors commonly customize them).
    """
    skip_files = set(skip_files or [])
    _assert_scaffold_paths_are_safe(
        (scaffold_managed_paths() | set(_BOOTSTRAP_FILES)) - skip_files
    )

    written = []
    skipped = []

    try:
        bootstrap_written, bootstrap_skipped = _bootstrap_authored_files(skip_files)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    written.extend(bootstrap_written)
    skipped.extend(bootstrap_skipped)

    for relative_path in _TEMPLATE_FILES:
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        if _copy_template_file(relative_path, overwrite):
            written.append(relative_path)
        else:
            skipped.append(relative_path)

    for relative_path, contents_factory in _GENERATED_FILES.items():
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        if _write_generated_file(relative_path, contents_factory(), overwrite):
            written.append(relative_path)
        else:
            skipped.append(relative_path)

    for relative_path in _TEMPLATE_DIRECTORIES:
        if relative_path in skip_files:
            skipped.append(relative_path)
            continue

        destination = Path(relative_path)
        with resources.as_file(_experiment_script_resource(relative_path)) as path:
            if destination.exists() and not overwrite:
                if _copy_missing_directory_entries(path, destination):
                    written.append(relative_path)
                else:
                    skipped.append(relative_path)
                continue

            if overwrite and _template_directory_matches(relative_path):
                skipped.append(relative_path)
                continue

            if overwrite and destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(
                path,
                destination,
                dirs_exist_ok=True,
            )
        written.append(relative_path)

    if "docker" not in skip_files and _make_docker_entries_executable():
        if "docker" in skipped:
            skipped.remove("docker")
        if "docker" not in written:
            written.append("docker")

    if overwrite:
        # Remove obsolete directories only when they still match the old template.
        for directory, hash_ in _REMOVABLE_DIRECTORIES:
            if Path(directory).exists() and md5_directory(directory) == hash_:
                shutil.rmtree(directory)
                written.append(directory)

    _report_scaffold_result(written, overwrite=overwrite)

    return {"written": written, "skipped": skipped}


def prune_experiment_scaffold(*, preserve_files=None, force=False):
    """Remove unmodified scaffold files while preserving authored experiment files."""
    preserve_files = set(preserve_files or [])
    managed_paths = scaffold_managed_paths()
    _assert_scaffold_paths_are_safe(managed_paths - preserve_files)
    preserved_unrecognized = []
    removed = []

    for relative_path in sorted(
        managed_paths - set(_TEMPLATE_DIRECTORIES) - preserve_files
    ):
        path = Path(relative_path)
        if path.exists():
            matches_scaffold = _managed_path_matches_scaffold(relative_path)
            if not force and not matches_scaffold:
                preserved_unrecognized.append(relative_path)
                continue
            path.unlink()
            removed.append(relative_path)
            _remove_empty_parent_dirs(path.parent)

    for relative_path in _TEMPLATE_DIRECTORIES:
        if relative_path in preserve_files:
            continue
        path = Path(relative_path)
        if path.exists():
            if not force and not _managed_path_matches_scaffold(relative_path):
                preserved_unrecognized.append(relative_path)
                continue
            shutil.rmtree(path)
            removed.append(relative_path)

    if removed:
        click.echo(
            "Removed scaffold-managed boilerplate: " + ", ".join(sorted(removed))
        )
    elif not preserved_unrecognized:
        click.echo("Nothing to prune; no matching scaffold-managed files found.")

    if preserved_unrecognized:
        click.echo(
            "Preserved scaffold paths that differ from current PsyNet templates:"
        )
        for relative_path in sorted(preserved_unrecognized):
            click.echo(f"  - {relative_path}")
        click.echo(
            "These paths may be customized or generated by another PsyNet version."
        )
        click.echo(
            "If you are sure you want to delete them, run "
            "'psynet scripts prune --force'."
        )

    _remove_empty_resource_directories()

    return {
        "preserved_unrecognized": preserved_unrecognized,
        "removed": removed,
    }
