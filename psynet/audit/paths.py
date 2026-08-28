"""Resolve and validate filesystem paths used by experiment audits."""

from __future__ import annotations

from pathlib import Path

SOURCE_BASES = {"packet", "packet_parent"}
PROTECTED_PACKET_DIRECTORIES = ("artifacts", "analyses", "logs")


def _has_audit_manifest(candidate: Path) -> bool:
    """Return whether ``candidate/audit.json`` exists."""

    return (candidate / "audit.json").is_file()


def resolve_audit_dir(
    path: Path | str | None = None,
    *,
    for_init: bool = False,
    require_manifest: bool = False,
) -> Path:
    """Resolve an audit packet directory from a CLI path argument."""

    if path is None:
        cwd = Path(".")
        if for_init:
            return cwd / "audit"
        if _has_audit_manifest(cwd):
            return cwd
        resolved = cwd / "audit"
    else:
        requested = Path(path)
        if for_init:
            return requested
        if _has_audit_manifest(requested):
            resolved = requested
        else:
            nested = requested / "audit"
            resolved = nested if _has_audit_manifest(nested) else requested

    if require_manifest and not _has_audit_manifest(resolved):
        display = Path(path) if path is not None else Path(".")
        raise ValueError(
            f"No audit packet found at {display}; "
            "expected audit.json or audit/audit.json",
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


def effective_source_base(audit_dir: Path, source_base: object) -> str | None:
    """Return an explicit source base or infer the legacy packet layout."""

    if source_base in SOURCE_BASES:
        return str(source_base)
    if source_base is None:
        return "packet_parent" if audit_dir.name == "audit" else "packet"
    return None


def experiment_source_root(
    audit_dir: Path,
    source_path: object,
    source_base: object,
) -> tuple[Path | None, list[str]]:
    """Resolve an experiment source path from its explicit base."""

    manifest_path = audit_dir / "audit.json"
    label = f"{manifest_path}: experiment.source_path"
    resolved_source_base = effective_source_base(audit_dir, source_base)
    if resolved_source_base is None:
        allowed = ", ".join(sorted(SOURCE_BASES))
        return None, [
            f"{manifest_path}: experiment.source_base must be one of: {allowed}"
        ]
    if not isinstance(source_path, str) or not source_path:
        return None, [f"{label}: path must be a non-empty string"]

    relative_path = Path(source_path)
    if relative_path.is_absolute():
        return None, [f"{label}: path must be relative to its source base"]

    root = audit_dir if resolved_source_base == "packet" else audit_dir.parent
    root = root.resolve()
    resolved_path = (root / relative_path).resolve()
    if not resolved_path.is_relative_to(root):
        return None, [f"{label}: path must stay inside its source base"]
    return resolved_path, []
