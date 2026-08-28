"""Resolve and validate filesystem paths used by experiment audits."""

from __future__ import annotations

from pathlib import Path

PROTECTED_PACKET_DIRECTORIES = ("artifacts", "analyses", "logs")


def _has_audit_manifest(candidate: Path) -> bool:
    """Return whether ``candidate/audit.json`` exists."""

    return (candidate / "audit.json").is_file()


def _is_named_audit(path: Path) -> bool:
    """Return whether ``path`` is the nested ``audit/`` folder."""

    name = path.name
    if name in ("", ".", ".."):
        return path.resolve().name == "audit"
    return name == "audit"


def _flat_packet_error(location: Path) -> ValueError:
    """Return an error for a leftover flat ``audit.json`` layout."""

    destination = location / "audit" / "audit.json"
    return ValueError(
        "Audits must live in ./audit/. Found audit.json at "
        f"{location}; move it to {destination}"
    )


def resolve_audit_dir(
    path: Path | str | None = None,
    *,
    for_init: bool = False,
    require_manifest: bool = False,
) -> Path:
    """Resolve the nested ``audit/`` directory from a CLI path argument.

    ``path`` is the experiment root unless it is already the ``audit/``
    folder. ``for_init`` always returns ``<experiment>/audit``.
    """

    if for_init:
        experiment = Path(path) if path is not None else Path(".")
        return experiment / "audit"

    if path is None:
        cwd = Path(".")
        if _has_audit_manifest(cwd) and _is_named_audit(cwd):
            resolved = cwd
        elif _has_audit_manifest(cwd / "audit"):
            resolved = cwd / "audit"
        elif _has_audit_manifest(cwd):
            raise _flat_packet_error(cwd)
        else:
            resolved = cwd / "audit"
    else:
        requested = Path(path)
        if _has_audit_manifest(requested) and _is_named_audit(requested):
            resolved = requested
        elif _has_audit_manifest(requested / "audit"):
            resolved = requested / "audit"
        elif _has_audit_manifest(requested):
            raise _flat_packet_error(requested)
        else:
            resolved = requested if _is_named_audit(requested) else requested / "audit"

    if require_manifest and not _has_audit_manifest(resolved):
        display = Path(path) if path is not None else Path(".")
        raise ValueError(
            f"No audit packet found at {display}; expected audit/audit.json",
        )
    return resolved


def relative_audit_path(
    audit_dir: Path,
    path_text: object,
    label: str,
) -> tuple[Path | None, list[str]]:
    """Resolve a manifest path and ensure it stays inside the bundle."""

    if not isinstance(path_text, str) or not path_text:
        return None, [f"{label}: path must be a non-empty string"]

    relative_path = Path(path_text)
    if relative_path.is_absolute():
        return None, [
            f"{label}: path must be relative to the experiment audit directory"
        ]

    audit_root = audit_dir.resolve()
    resolved_path = (audit_dir / relative_path).resolve()
    if not resolved_path.is_relative_to(audit_root):
        return None, [f"{label}: path must stay inside the experiment audit directory"]
    return resolved_path, []


def validate_audit_site_dir(
    audit_dir: Path,
    site_dir: Path,
    label: str,
) -> list[str]:
    """Reject output directories that overlap audit packet inputs."""

    audit_root = audit_dir.resolve()
    resolved_site = site_dir.resolve()
    if not resolved_site.is_relative_to(audit_root):
        return []

    if resolved_site == audit_root:
        return [
            f"{label}: must use a dedicated output directory that does not "
            "overlap audit packet inputs"
        ]

    protected = [audit_root / name for name in PROTECTED_PACKET_DIRECTORIES]
    if any(
        resolved_site == path
        or resolved_site.is_relative_to(path)
        or path.is_relative_to(resolved_site)
        for path in protected
    ):
        return [
            f"{label}: must use a dedicated output directory that does not "
            "overlap audit packet inputs"
        ]
    return []


def experiment_source_root(
    audit_dir: Path,
    source_path: object,
) -> tuple[Path | None, list[str]]:
    """Resolve experiment source relative to the parent of ``audit/``."""

    manifest_path = audit_dir / "audit.json"
    label = f"{manifest_path}: experiment.source_path"
    if not isinstance(source_path, str) or not source_path:
        return None, [f"{label}: path must be a non-empty string"]

    relative_path = Path(source_path)
    if relative_path.is_absolute():
        return None, [f"{label}: path must be relative to the experiment directory"]

    root = audit_dir.resolve().parent
    resolved_path = (root / relative_path).resolve()
    if not resolved_path.is_relative_to(root):
        return None, [f"{label}: path must stay inside the experiment directory"]
    return resolved_path, []
