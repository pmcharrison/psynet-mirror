"""Package and render PsyNet experiment audit bundles."""

from __future__ import annotations

import html
import json
import platform
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psynet.audit.artifacts import (
    HASHED_ARTIFACTS_DIR,
    MONITOR_STATIC_ARTIFACTS_DIR,
    redact_known_credentials,
    write_hashed_artifact,
    write_shared_monitor_static_assets,
)
from psynet.audit.html import (
    pygments_css,
    render_completeness,
    render_evidence_section,
    render_json_block,
    render_markdown_block,
    render_visible_artifacts,
    safe_section_html,
)
from psynet.audit.html import (
    render_timeline_section as render_shared_timeline_section,
)
from psynet.audit.model import (
    TEXT_AUDIT_EXTENSIONS,
    AuditFile,
    classify_audit_evidence,
    file_kind,
)
from psynet.audit.timeline import parse_timeline_entries
from psynet.audit.video import validate_evidence_video

AUDIT_TOP_LEVEL_REQUIRED = {
    "schema_version",
    "created_at",
    "updated_at",
    "experiment",
    "implementation",
    "environment",
    "sections",
    "artifacts",
    "checks",
    "blockers",
}
DEFAULT_AUDIT_PROFILE = "psynet.core"
# Core does not register workshop plugins. Declared extension ids are opaque to
# PsyNet validate/render. Documented external ids are ignored silently; other
# unknown ids warn but do not fail.
CORE_KNOWN_EXTENSION_IDS: frozenset[str] = frozenset()
DOCUMENTED_EXTERNAL_EXTENSION_IDS: frozenset[str] = frozenset(
    {
        "psynetskills.challenge",
    }
)
SECTION_REQUIRED_FIELDS = {"id", "title", "kind"}
SECTION_KINDS = {
    "markdown",
    "evidence",
    "files",
    "timeline",
    "json",
    "checks",
    "blockers",
}
PLAN_SECTION_ID = "plan"
PLAN_SECTION_PATH = "PLAN.md"
ARTIFACT_REQUIRED_FIELDS = {
    "id",
    "kind",
    "path",
    "title",
    "description",
    "required",
    "status",
    "created_by",
}
BLOCKER_REQUIRED_FIELDS = {"artifact_id", "severity", "reason", "next_step"}
CHECK_REQUIRED_FIELDS = {"id", "title", "status"}
ARTIFACT_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
ARTIFACT_KINDS = {
    "video",
    "screenshot",
    "notebook",
    "data_export",
    "performance",
    "monitor_snapshot",
    "log",
    "report",
    "source",
    "other",
}
ARTIFACT_STATUSES = {"present", "missing", "blocked", "not_applicable"}
ARTIFACT_CREATORS = {"agent", "cli", "manual", "unknown"}
BLOCKER_SEVERITIES = {"warning", "error"}
CHECK_STATUSES = {"pass", "fail", "warning", "not_run"}
MAX_AUDIT_NOTEBOOK_BYTES = 100_000
CLI_NAME = "psynet audit"
AUDIT_CSS_OUTPUT = "css/audit.css"
AUDIT_DIR_HELP = (
    "Audit packet directory or experiment root. When omitted (or when the path "
    "is an experiment root), auto-detects ./audit.json or ./audit/audit.json."
)
SOURCE_PATH_HELP = (
    "Path to the experiment directory that contains the audit folder, relative "
    "to the audit directory's parent (default: .). Run init from the experiment "
    "root so ./audit/ is created and source_path stays ."
)


class AuditValidationError(ValueError):
    """Raised when render is blocked by validation problems."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


def format_allowed(values: set[str] | frozenset[str]) -> str:
    """Format allowed enum values for validation errors."""

    return ", ".join(sorted(values))


def artifact_label(audit_dir: Path, index: int, artifact_id: object) -> str:
    """Return a human-oriented label for an artifact validation error."""

    base = f"{audit_dir / 'audit.json'}: artifacts[{index}]"
    if isinstance(artifact_id, str) and artifact_id:
        return f"{base} (id={artifact_id})"
    return base


def _has_audit_manifest(candidate: Path) -> bool:
    """Return whether ``candidate/audit.json`` exists."""

    return (candidate / "audit.json").is_file()


def resolve_audit_dir(
    path: Path | str | None = None,
    *,
    for_init: bool = False,
) -> Path:
    """Resolve an audit packet directory from a CLI path argument.

    When ``path`` is omitted, prefer the current directory if it already
    contains ``audit.json`` (challenge attempt root or cwd inside the packet),
    otherwise use ``./audit`` (standalone experiment layout). Default ``init``
    always targets ``./audit``.

    When ``path`` is given for validate/render/mark-present, use it if it
    contains ``audit.json``; otherwise, if ``path/audit/audit.json`` exists, use
    that nested packet. This lets ``psynet audit validate .`` work from an
    experiment root that holds ``./audit/``. Explicit ``init`` paths are never
    redirected: ``init .`` still creates a flat packet in the current directory.
    """

    if path is None:
        cwd = Path(".")
        if for_init:
            return cwd / "audit"
        if _has_audit_manifest(cwd):
            return cwd
        return cwd / "audit"

    requested = Path(path)
    if for_init:
        return requested
    if _has_audit_manifest(requested):
        return requested
    nested = requested / "audit"
    if _has_audit_manifest(nested):
        return nested
    return requested


def count_blockers(manifest: dict[str, Any]) -> int:
    """Return the number of blocker records in a manifest."""

    blockers = manifest.get("blockers")
    return len(blockers) if isinstance(blockers, list) else 0


def validate_success_message(
    audit_dir: Path, manifest: dict[str, Any] | None = None
) -> str:
    """Return the validate success line, including blocker count when known."""

    if manifest is None:
        try:
            manifest = read_audit_manifest(audit_dir)
        except (OSError, ValueError, json.JSONDecodeError):
            return f"Audit packet coherent: {audit_dir}"
    n = count_blockers(manifest)
    if n:
        return (
            f"Audit packet coherent: {audit_dir} "
            f"({n} blocker{'s' if n != 1 else ''} recorded; readiness incomplete)"
        )
    return f"Audit packet coherent: {audit_dir} (no blockers)"


def init_success_messages(audit_dir: Path, prog: str = CLI_NAME) -> list[str]:
    """Return user-facing lines printed after a successful init."""

    return [
        f"Initialized experiment audit directory: {audit_dir}",
        "This is a starter packet: validate can pass while required evidence is "
        "still blocked (packet coherent ≠ experiment ready). Fill artifacts, then "
        f"mark them present (see `{prog} mark-present`).",
        "Required artifacts use status blocked + a blocker; optional gaps may use "
        "missing without a blocker.",
        f"Next: {prog} validate",
        f"Next: {prog} render",
    ]


def audit_css_path() -> Path:
    """Return the packaged audit stylesheet path."""
    from importlib import resources

    return Path(resources.files("psynet") / "resources" / "audit" / "audit.css")


STARTER_PROMPT = """# Prompt

Summarize the original request or experiment brief.
"""
STARTER_PLAN = """# Plan

Summarize the implementation plan for this experiment audit.
"""
STARTER_TIMELINE = """# Timeline

Record notable implementation and evidence-collection events, or remove this
section from `audit.json`.

Use entries such as:

`- T+00:00:00 [agent-start] Started implementation.`
"""
STARTER_REPORT = """# Experiment audit report

Summarize the implementation, validation, analysis, and any unresolved issues.
"""


def read_audit_manifest(audit_dir: Path) -> dict[str, Any]:
    """Read the experiment audit manifest from an experiment audit directory."""

    manifest_path = audit_dir / "audit.json"
    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: manifest must be a JSON object")
    return manifest


def display_title_from_path(audit_dir: Path) -> str:
    """Derive a human-readable experiment title from an audit path."""

    resolved = audit_dir.resolve()
    source = resolved.parent if resolved.name == "audit" else resolved
    normalized = re.sub(r"[-_]+", " ", source.name).strip()
    return normalized.title() if normalized else "Experiment Audit"


def audit_display_title(audit_dir: Path, manifest: dict[str, Any]) -> str:
    """Return the display title for an experiment audit."""

    experiment = manifest.get("experiment")
    if isinstance(experiment, dict):
        title = experiment.get("title")
        if isinstance(title, str) and title.strip():
            return title
    return display_title_from_path(audit_dir)


def utc_timestamp() -> str:
    """Return a UTC ISO timestamp for generated audit metadata."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def starter_artifact(
    artifact_id: str,
    kind: str,
    path: str,
    title: str,
    description: str,
    *,
    required: bool,
    status: str,
    created_by: str = "unknown",
) -> dict[str, object]:
    """Create a starter artifact record."""

    return {
        "id": artifact_id,
        "kind": kind,
        "path": path,
        "title": title,
        "description": description,
        "required": required,
        "status": status,
        "created_by": created_by,
    }


def starter_blocker(artifact_id: str, reason: str, next_step: str) -> dict[str, str]:
    """Create a starter blocker for an incomplete required artifact."""

    return {
        "artifact_id": artifact_id,
        "severity": "error",
        "reason": reason,
        "next_step": next_step,
    }


def starter_section(
    section_id: str,
    title: str,
    kind: str,
    *,
    path: str | None = None,
    display: bool = True,
) -> dict[str, object]:
    """Create a starter audit section."""

    section: dict[str, object] = {
        "id": section_id,
        "title": title,
        "kind": kind,
        "display": display,
    }
    if path is not None:
        section["path"] = path
    return section


def audit_profile(manifest: dict[str, Any]) -> str:
    """Return the effective audit profile, defaulting to the core profile."""

    profile = manifest.get("profile", DEFAULT_AUDIT_PROFILE)
    if isinstance(profile, str) and profile.strip():
        return profile.strip()
    return DEFAULT_AUDIT_PROFILE


def starter_audit_manifest(source_path: str) -> dict[str, object]:
    """Create a starter experiment audit manifest."""

    timestamp = utc_timestamp()
    return {
        "schema_version": "1.0",
        "created_at": timestamp,
        "updated_at": timestamp,
        "profile": DEFAULT_AUDIT_PROFILE,
        "extensions": [],
        "experiment": {
            "source_path": source_path,
        },
        "implementation": {
            "summary": "TODO: Summarize the experiment implementation.",
        },
        "environment": {
            "os": platform.system().lower(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "sections": [
            starter_section("prompt", "Prompt", "markdown", path="PROMPT.md"),
            starter_section("plan", "Plan", "markdown", path="PLAN.md"),
            starter_section("timeline", "Timeline", "timeline", path="TIMELINE.md"),
            starter_section("report", "Report", "markdown", path="REPORT.md"),
            starter_section("blockers", "Blockers", "blockers"),
            starter_section("evidence", "Evidence", "evidence"),
            starter_section("files", "Additional files", "files"),
            starter_section("checks", "Checks", "checks"),
        ],
        "artifacts": [
            starter_artifact(
                "participant_video",
                "video",
                "artifacts/participant.mp4",
                "Participant walkthrough",
                "Participant-facing walkthrough video.",
                required=True,
                status="blocked",
            ),
            starter_artifact(
                "screenshots",
                "screenshot",
                "artifacts/screenshots/manifest.json",
                "Screenshot walkthrough",
                "Manifest describing targeted participant-facing screenshots.",
                required=False,
                status="missing",
            ),
            starter_artifact(
                "performance_result",
                "performance",
                "artifacts/performance.json",
                "Performance test result",
                "PsyNet performance-test output.",
                required=True,
                status="blocked",
            ),
            starter_artifact(
                "monitor_snapshot",
                "monitor_snapshot",
                "artifacts/monitor.html",
                "Monitor snapshot",
                "Static PsyNet monitor snapshot.",
                required=True,
                status="blocked",
            ),
            starter_artifact(
                "simulation_export",
                "data_export",
                "artifacts/simulated_data.zip",
                "Simulated data export",
                "Data export produced by simulated participants.",
                required=True,
                status="blocked",
            ),
            starter_artifact(
                "analysis_notebook",
                "notebook",
                "analyses/analysis.ipynb",
                "Analysis notebook",
                "Executed notebook that reads the simulated export and summarizes results.",
                required=True,
                status="blocked",
            ),
        ],
        "checks": [],
        "blockers": [
            starter_blocker(
                "participant_video",
                "Participant walkthrough has not been recorded yet.",
                "Record or explicitly mark participant video as not applicable.",
            ),
            starter_blocker(
                "performance_result",
                "Performance test has not been run yet.",
                "Run psynet performance-test local … --audit (or --audit <packet>).",
            ),
            starter_blocker(
                "monitor_snapshot",
                "Monitor snapshot has not been captured yet.",
                "Capture a static PsyNet monitor snapshot at artifacts/monitor.html.",
            ),
            starter_blocker(
                "simulation_export",
                "Simulation export has not been produced yet.",
                "Run psynet simulate, then zip data/simulated_data/ to "
                "artifacts/simulated_data.zip (simulate does not write the audit path).",
            ),
            starter_blocker(
                "analysis_notebook",
                "Analysis notebook has not been executed yet.",
                "Create and execute analyses/analysis.ipynb.",
            ),
        ],
        "render": {
            "site_path": "site",
            "generator": CLI_NAME,
        },
    }


def init_audit(audit_dir: Path, source_path: str = ".", force: bool = False) -> None:
    """Create a starter experiment audit directory."""

    manifest_path = audit_dir / "audit.json"
    if manifest_path.exists() and not force:
        raise FileExistsError(
            f"{manifest_path}: already exists; pass --force to replace it"
        )

    for directory in (
        audit_dir,
        audit_dir / "artifacts",
        audit_dir / "artifacts" / "screenshots",
        audit_dir / "analyses",
        audit_dir / "logs",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(
        json.dumps(starter_audit_manifest(source_path), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / "REPORT.md").write_text(STARTER_REPORT, encoding="utf-8")
    (audit_dir / "PROMPT.md").write_text(STARTER_PROMPT, encoding="utf-8")
    (audit_dir / "PLAN.md").write_text(STARTER_PLAN, encoding="utf-8")
    (audit_dir / "TIMELINE.md").write_text(STARTER_TIMELINE, encoding="utf-8")


def relative_audit_path(
    audit_dir: Path,
    path_text: object,
    label: str,
) -> tuple[Path | None, list[str]]:
    """Resolve a manifest path and ensure it stays inside the bundle directory."""

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


def validate_audit_notebook(notebook_file: Path) -> list[str]:
    """Validate that an audit notebook is parseable and small enough to render."""

    problems: list[str] = []
    size_bytes = notebook_file.stat().st_size
    if size_bytes > MAX_AUDIT_NOTEBOOK_BYTES:
        problems.append(
            f"{notebook_file}: audit notebooks must be at most "
            f"{MAX_AUDIT_NOTEBOOK_BYTES} bytes",
        )
    try:
        notebook = json.loads(notebook_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append(f"{notebook_file}: invalid notebook JSON: {exc}")
        return problems
    if not isinstance(notebook, dict):
        problems.append(f"{notebook_file}: notebook must be a JSON object")
    return problems


def validate_audit_blockers(
    audit_dir: Path,
    manifest: dict[str, Any],
) -> tuple[set[str], list[str]]:
    """Validate blocker records and return the artifact IDs they cover."""

    blockers = manifest.get("blockers")
    if not isinstance(blockers, list):
        return set(), [f"{audit_dir / 'audit.json'}: blockers must be a list"]

    blocker_ids: set[str] = set()
    problems: list[str] = []
    for index, blocker in enumerate(blockers):
        label = f"{audit_dir / 'audit.json'}: blockers[{index}]"
        if not isinstance(blocker, dict):
            problems.append(f"{label}: blocker must be a JSON object")
            continue
        for field in sorted(BLOCKER_REQUIRED_FIELDS):
            if field not in blocker:
                problems.append(f"{label}: missing {field}")
        artifact_id = blocker.get("artifact_id")
        if not isinstance(artifact_id, str) or not ARTIFACT_ID_RE.fullmatch(
            artifact_id
        ):
            problems.append(f"{label}: artifact_id must be a valid artifact ID")
        else:
            blocker_ids.add(artifact_id)
        if blocker.get("severity") not in BLOCKER_SEVERITIES:
            problems.append(f"{label}: severity must be warning or error")
        for field in ("reason", "next_step"):
            if not isinstance(blocker.get(field), str) or not blocker[field].strip():
                problems.append(f"{label}: {field} must be a non-empty string")
    return blocker_ids, problems


def validate_audit_checks(audit_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Validate check records in an experiment audit manifest."""

    checks = manifest.get("checks")
    if not isinstance(checks, list):
        return [f"{audit_dir / 'audit.json'}: checks must be a list"]

    problems: list[str] = []
    for index, check in enumerate(checks):
        label = f"{audit_dir / 'audit.json'}: checks[{index}]"
        if not isinstance(check, dict):
            problems.append(f"{label}: check must be a JSON object")
            continue
        for field in sorted(CHECK_REQUIRED_FIELDS):
            if field not in check:
                problems.append(f"{label}: missing {field}")
        check_id = check.get("id")
        if not isinstance(check_id, str) or not ARTIFACT_ID_RE.fullmatch(check_id):
            problems.append(f"{label}: id must be a valid check ID")
        if not isinstance(check.get("title"), str) or not check["title"].strip():
            problems.append(f"{label}: title must be a non-empty string")
        if check.get("status") not in CHECK_STATUSES:
            problems.append(
                f"{label}: status must be pass, fail, warning, or not_run",
            )
    return problems


def validate_audit_sections(audit_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Validate section records in an experiment audit manifest."""

    sections = manifest.get("sections")
    if not isinstance(sections, list):
        return [f"{audit_dir / 'audit.json'}: sections must be a list"]

    problems: list[str] = []
    section_ids: set[str] = set()
    for index, section in enumerate(sections):
        label = f"{audit_dir / 'audit.json'}: sections[{index}]"
        if not isinstance(section, dict):
            problems.append(f"{label}: section must be a JSON object")
            continue
        for field in sorted(SECTION_REQUIRED_FIELDS):
            if field not in section:
                problems.append(f"{label}: missing {field}")

        section_id = section.get("id")
        if not isinstance(section_id, str) or not ARTIFACT_ID_RE.fullmatch(section_id):
            problems.append(f"{label}: id must be a valid section ID")
        elif section_id in section_ids:
            problems.append(f"{label}: duplicate section ID {section_id!r}")
        else:
            section_ids.add(section_id)

        if not isinstance(section.get("title"), str) or not section["title"].strip():
            problems.append(f"{label}: title must be a non-empty string")
        kind = section.get("kind")
        if kind not in SECTION_KINDS:
            problems.append(f"{label}: kind is not recognized")
        if "display" in section and not isinstance(section.get("display"), bool):
            problems.append(f"{label}: display must be a boolean")
        if kind in {"markdown", "timeline", "json"} and not isinstance(
            section.get("content"),
            str,
        ):
            section_path, path_problems = relative_audit_path(
                audit_dir,
                section.get("path"),
                f"{label}: path",
            )
            problems.extend(path_problems)
            if section_path is not None and section.get("display") is not False:
                if not section_path.is_file():
                    problems.append(f"{label}: section file is missing: {section_path}")
        elif "path" in section:
            _, path_problems = relative_audit_path(
                audit_dir,
                section.get("path"),
                f"{label}: path",
            )
            problems.extend(path_problems)
    return problems


def validate_audit_artifacts(
    audit_dir: Path,
    manifest: dict[str, Any],
    blocker_ids: set[str],
) -> list[str]:
    """Validate artifact records and their files."""

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return [f"{audit_dir / 'audit.json'}: artifacts must be a list"]

    problems: list[str] = []
    artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        artifact_id_hint = artifact.get("id") if isinstance(artifact, dict) else None
        label = artifact_label(audit_dir, index, artifact_id_hint)
        if not isinstance(artifact, dict):
            problems.append(f"{label}: artifact must be a JSON object")
            continue
        for field in sorted(ARTIFACT_REQUIRED_FIELDS):
            if field not in artifact:
                problems.append(f"{label}: missing {field}")

        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not ARTIFACT_ID_RE.fullmatch(
            artifact_id
        ):
            problems.append(f"{label}: id must be a valid artifact ID")
            artifact_id = None
        elif artifact_id in artifact_ids:
            problems.append(f"{label}: duplicate artifact ID {artifact_id!r}")
        else:
            artifact_ids.add(artifact_id)
            label = artifact_label(audit_dir, index, artifact_id)

        if artifact.get("kind") not in ARTIFACT_KINDS:
            problems.append(
                f"{label}: kind is not recognized "
                f"(allowed: {format_allowed(ARTIFACT_KINDS)})"
            )
        status = artifact.get("status")
        if status not in ARTIFACT_STATUSES:
            problems.append(
                f"{label}: status is not recognized "
                f"(allowed: {format_allowed(ARTIFACT_STATUSES)})"
            )
        if artifact.get("created_by") not in ARTIFACT_CREATORS:
            problems.append(
                f"{label}: created_by is not recognized "
                f"(allowed: {format_allowed(ARTIFACT_CREATORS)})"
            )
        if not isinstance(artifact.get("required"), bool):
            problems.append(f"{label}: required must be a boolean")
        for field in ("title", "description"):
            if not isinstance(artifact.get(field), str) or not artifact[field].strip():
                problems.append(f"{label}: {field} must be a non-empty string")

        artifact_path, path_problems = relative_audit_path(
            audit_dir,
            artifact.get("path"),
            label,
        )
        problems.extend(path_problems)
        if artifact_path is None:
            continue

        if status == "present":
            if not artifact_path.is_file():
                problems.append(
                    f"{label}: artifact marked present but file is missing: "
                    f"{artifact_path}",
                )
                continue
            if artifact_path.suffix.lower() == ".mp4":
                problems.extend(validate_evidence_video(artifact_path))
            if artifact_path.suffix.lower() == ".ipynb":
                problems.extend(validate_audit_notebook(artifact_path))

        if artifact.get("required") is True and status != "present":
            if artifact_id is None or artifact_id not in blocker_ids:
                problems.append(
                    f"{label}: required artifact must be present or have a "
                    "matching blocker",
                )
    return problems


def validate_audit_profile_and_extensions(
    audit_dir: Path,
    manifest: dict[str, Any],
) -> list[str]:
    """Validate profile and extensions fields (errors only)."""

    problems: list[str] = []
    manifest_path = audit_dir / "audit.json"
    if "profile" in manifest:
        profile = manifest.get("profile")
        if not isinstance(profile, str) or not profile.strip():
            problems.append(f"{manifest_path}: profile must be a non-empty string")
    if "extensions" in manifest:
        extensions = manifest.get("extensions")
        if not isinstance(extensions, list):
            problems.append(f"{manifest_path}: extensions must be a list")
        else:
            for index, extension_id in enumerate(extensions):
                if not isinstance(extension_id, str) or not extension_id.strip():
                    problems.append(
                        f"{manifest_path}: extensions[{index}] must be a non-empty string",
                    )
    if "extensions_meta" in manifest:
        extensions_meta = manifest.get("extensions_meta")
        if not isinstance(extensions_meta, dict):
            problems.append(f"{manifest_path}: extensions_meta must be a JSON object")
    return problems


def validate_core_plan_section(
    audit_dir: Path,
    manifest: dict[str, Any],
) -> list[str]:
    """Require a displayed plan markdown section for the default core profile."""

    if audit_profile(manifest) != DEFAULT_AUDIT_PROFILE:
        return []

    manifest_path = audit_dir / "audit.json"
    sections = manifest.get("sections")
    if not isinstance(sections, list):
        return []

    plan_sections = [
        section
        for section in sections
        if isinstance(section, dict) and section.get("id") == PLAN_SECTION_ID
    ]
    if not plan_sections:
        return [
            f"{manifest_path}: profile {DEFAULT_AUDIT_PROFILE!r} requires a "
            f"displayed markdown section with id {PLAN_SECTION_ID!r} "
            f"pointing at {PLAN_SECTION_PATH}",
        ]

    problems: list[str] = []
    plan = plan_sections[0]
    if plan.get("kind") != "markdown":
        problems.append(
            f"{manifest_path}: section id {PLAN_SECTION_ID!r} must have kind 'markdown'",
        )
    if plan.get("display") is False:
        problems.append(
            f"{manifest_path}: profile {DEFAULT_AUDIT_PROFILE!r} requires the "
            f"{PLAN_SECTION_ID!r} section to be displayed",
        )
    path = plan.get("path")
    if path != PLAN_SECTION_PATH and not (
        isinstance(plan.get("content"), str) and plan.get("content")
    ):
        problems.append(
            f"{manifest_path}: section id {PLAN_SECTION_ID!r} must use path "
            f"{PLAN_SECTION_PATH!r} (or inline content)",
        )
    return problems


def collect_audit_warnings(
    audit_dir: Path,
    manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Return non-fatal validation warnings for an experiment audit."""

    if manifest is None:
        try:
            manifest = read_audit_manifest(audit_dir)
        except (OSError, ValueError, json.JSONDecodeError):
            return []

    warnings: list[str] = []
    manifest_path = audit_dir / "audit.json"
    extensions = manifest.get("extensions", [])
    if not isinstance(extensions, list):
        return warnings
    for extension_id in extensions:
        if not isinstance(extension_id, str) or not extension_id.strip():
            continue
        if (
            extension_id not in CORE_KNOWN_EXTENSION_IDS
            and extension_id not in DOCUMENTED_EXTERNAL_EXTENSION_IDS
        ):
            warnings.append(
                f"{manifest_path}: unknown extension id {extension_id!r} "
                "(ignored by core validate/render)",
            )
    return warnings


def validate_audit_manifest(audit_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Validate experiment audit manifest structure and local artifact files."""

    problems: list[str] = []
    manifest_path = audit_dir / "audit.json"
    for field in sorted(AUDIT_TOP_LEVEL_REQUIRED):
        if field not in manifest:
            problems.append(f"{manifest_path}: missing {field}")

    if manifest.get("schema_version") != "1.0":
        problems.append(f"{manifest_path}: schema_version must be '1.0'")
    for field in ("created_at", "updated_at"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            problems.append(f"{manifest_path}: {field} must be a non-empty string")
    for field in ("experiment", "implementation", "environment"):
        if not isinstance(manifest.get(field), dict):
            problems.append(f"{manifest_path}: {field} must be a JSON object")

    if isinstance(manifest.get("experiment"), dict):
        experiment = manifest["experiment"]
        if "title" in experiment and (
            not isinstance(experiment.get("title"), str)
            or not experiment["title"].strip()
        ):
            problems.append(
                f"{manifest_path}: experiment.title must be a non-empty string"
            )
        if "source_path" not in experiment:
            problems.append(f"{manifest_path}: experiment missing source_path")
    if isinstance(manifest.get("implementation"), dict):
        implementation = manifest["implementation"]
        if (
            not isinstance(implementation.get("summary"), str)
            or not implementation["summary"].strip()
        ):
            problems.append(
                f"{manifest_path}: implementation.summary must be a non-empty string",
            )
    problems.extend(validate_audit_profile_and_extensions(audit_dir, manifest))
    problems.extend(validate_core_plan_section(audit_dir, manifest))
    blocker_ids, blocker_problems = validate_audit_blockers(audit_dir, manifest)
    problems.extend(blocker_problems)
    problems.extend(validate_audit_sections(audit_dir, manifest))
    problems.extend(validate_audit_checks(audit_dir, manifest))
    problems.extend(validate_audit_artifacts(audit_dir, manifest, blocker_ids))

    render = manifest.get("render")
    if isinstance(render, dict) and "site_path" in render:
        _, site_problems = relative_audit_path(
            audit_dir,
            render.get("site_path"),
            f"{audit_dir / 'audit.json'}: render.site_path",
        )
        problems.extend(site_problems)
    return problems


def validate_audit(audit_dir: Path) -> list[str]:
    """Validate a standalone experiment audit directory."""

    manifest_path = audit_dir / "audit.json"
    if not manifest_path.exists():
        return [f"{manifest_path}: missing experiment audit manifest"]
    try:
        manifest = read_audit_manifest(audit_dir)
    except json.JSONDecodeError as exc:
        return [f"{manifest_path}: invalid JSON: {exc}"]
    except ValueError as exc:
        return [str(exc)]
    return validate_audit_manifest(audit_dir, manifest)


def artifact_output_url(relative_url: str) -> str:
    """Return a browser path from a rendered audit page to a published artifact."""

    return f"static/{relative_url}"


def publish_audit_artifacts(
    audit_dir: Path,
    site_dir: Path,
    manifest: dict[str, Any],
) -> list[AuditFile]:
    """Publish present artifacts and return render metadata."""

    target_root = site_dir / "static" / HASHED_ARTIFACTS_DIR
    shared_static_root = site_dir / "static" / MONITOR_STATIC_ARTIFACTS_DIR
    shutil.rmtree(target_root, ignore_errors=True)
    shutil.rmtree(shared_static_root, ignore_errors=True)
    target_root.mkdir(parents=True, exist_ok=True)
    write_shared_monitor_static_assets(shared_static_root)

    rendered: list[AuditFile] = []
    published_paths: set[str] = set()
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        relative_path = str(artifact.get("path") or "")
        status = str(artifact.get("status") or "missing")
        if not relative_path or status != "present":
            continue
        source_file, path_problems = relative_audit_path(
            audit_dir,
            relative_path,
            f"artifact {artifact.get('id')!r}",
        )
        if path_problems or source_file is None or not source_file.is_file():
            continue
        artifact_url = artifact_output_url(
            write_hashed_artifact(
                source_file,
                target_root,
                HASHED_ARTIFACTS_DIR,
            ),
        )
        rendered.append(
            AuditFile(
                path=relative_path,
                url=artifact_url,
                content=read_audit_artifact_content(source_file),
                size_bytes=source_file.stat().st_size,
                kind=file_kind(relative_path),
            )
        )
        published_paths.add(relative_path)
        if relative_path.endswith("screenshots/manifest.json"):
            rendered.extend(
                publish_screenshot_manifest_files(
                    audit_dir,
                    target_root,
                    source_file,
                    published_paths,
                )
            )
    return rendered


def publish_screenshot_manifest_files(
    audit_dir: Path,
    target_root: Path,
    manifest_file: Path,
    published_paths: set[str],
) -> list[AuditFile]:
    """Publish screenshot files referenced by a screenshot caption manifest."""

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    captions = data.get("captions") if isinstance(data, dict) else None
    if not isinstance(captions, dict):
        return []

    rendered: list[AuditFile] = []
    for caption_path in captions:
        if not isinstance(caption_path, str):
            continue
        relative_path = (
            caption_path
            if caption_path.startswith("artifacts/")
            else f"artifacts/{caption_path}"
        )
        if relative_path in published_paths:
            continue
        source_file, problems = relative_audit_path(
            audit_dir,
            relative_path,
            f"screenshot manifest path {caption_path!r}",
        )
        if (
            problems
            or source_file is None
            or not source_file.is_file()
            or source_file.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
        ):
            continue
        artifact_url = artifact_output_url(
            write_hashed_artifact(
                source_file,
                target_root,
                HASHED_ARTIFACTS_DIR,
            )
        )
        rendered.append(
            AuditFile(
                path=relative_path,
                url=artifact_url,
                content=None,
                size_bytes=source_file.stat().st_size,
                kind=file_kind(relative_path),
            )
        )
        published_paths.add(relative_path)
    return rendered


def read_audit_artifact_content(
    source_file: Path, max_bytes: int = 100_000
) -> str | None:
    """Read text artifact content for audit classification."""

    if source_file.suffix.lower() not in TEXT_AUDIT_EXTENSIONS:
        return None
    try:
        data = source_file.read_bytes()
    except OSError:
        return None
    if len(data) > max_bytes:
        data = data[:max_bytes]
    try:
        return redact_known_credentials(data.decode("utf-8"))
    except UnicodeDecodeError:
        return None


def render_metadata_grid(items: list[tuple[str, str]]) -> str:
    """Render a dashboard-style metadata grid."""

    rows = []
    for label, value in items:
        rows.append(
            f"<div><dt>{html.escape(label)}</dt><dd>{value}</dd></div>",
        )
    return '<dl class="metadata-grid attempt-summary">' + "".join(rows) + "</dl>"


def render_metadata_value(value: object, fallback: str = "-") -> str:
    """Render one metadata value."""

    if value is None or value == "":
        return html.escape(fallback)
    return html.escape(str(value))


def render_metadata_code(value: object, fallback: str = "-") -> str:
    """Render one metadata value as code."""

    return f"<code>{render_metadata_value(value, fallback)}</code>"


def write_audit_static_assets(site_dir: Path) -> str:
    """Write static experiment audit CSS and return its page-relative URL."""

    target = site_dir / "static" / AUDIT_CSS_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    css = audit_css_path().read_text(encoding="utf-8")
    target.write_text(f"{css}\n\n{pygments_css()}\n", encoding="utf-8")
    return f"static/{AUDIT_CSS_OUTPUT}"


def display_sections(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return displayable section records in manifest order."""

    sections = manifest.get("sections")
    if not isinstance(sections, list):
        return []
    checks = manifest.get("checks")
    return [
        section
        for section in sections
        if isinstance(section, dict)
        and section.get("display") is not False
        and not (
            section.get("kind") == "checks"
            and (not isinstance(checks, list) or not checks)
        )
    ]


def section_panel_class(section: dict[str, Any]) -> str:
    """Return the section-specific panel class."""

    section_id = str(section.get("id") or "")
    kind = str(section.get("kind") or "")
    if section_id == "report":
        return "report-panel"
    if section_id == "plan":
        return "plan-panel"
    if kind == "evidence":
        return "evidence-panel"
    return ""


def render_markdown_section(audit_dir: Path, section: dict[str, Any]) -> str:
    """Render one markdown section."""

    content = section.get("content")
    if isinstance(content, str):
        return render_markdown_block(strip_redundant_section_heading(content, section))
    section_path, problems = relative_audit_path(
        audit_dir,
        section.get("path"),
        f"{audit_dir / 'audit.json'}: sections[{section.get('id', '')}].path",
    )
    if problems or section_path is None:
        return '<p class="missing">Section path is invalid.</p>'
    if not section_path.is_file():
        return '<p class="missing">Section file missing.</p>'
    content = section_path.read_text(encoding="utf-8")
    return render_markdown_block(strip_redundant_section_heading(content, section))


def strip_redundant_section_heading(
    markdown: str,
    _section: dict[str, Any],
) -> str:
    """Remove a leading H1 because the enclosing panel already provides one."""

    pattern = re.compile(r"\A\s*#\s+.+?\s*(?:\n+|\Z)")
    return pattern.sub("", markdown, count=1)


def section_text(audit_dir: Path, section: dict[str, Any]) -> str | None:
    """Return inline or file-backed section text."""

    content = section.get("content")
    if isinstance(content, str):
        return content
    section_path, problems = relative_audit_path(
        audit_dir,
        section.get("path"),
        f"{audit_dir / 'audit.json'}: sections[{section.get('id', '')}].path",
    )
    if problems or section_path is None or not section_path.is_file():
        return None
    return section_path.read_text(encoding="utf-8")


def render_timeline_section(audit_dir: Path, section: dict[str, Any]) -> str:
    """Render one timeline section."""

    text = section_text(audit_dir, section)
    if text is None:
        return '<p class="missing">Timeline section file missing.</p>'
    entries = parse_timeline_entries(text)
    return render_shared_timeline_section(
        entries,
        fallback_markdown=strip_redundant_section_heading(text, section),
    )


def render_json_section(audit_dir: Path, section: dict[str, Any]) -> str:
    """Render one JSON or metadata section."""

    text = section_text(audit_dir, section)
    if text is None:
        return '<p class="missing">JSON section file missing.</p>'
    return render_json_block(text)


def section_paths(manifest: dict[str, Any]) -> set[str]:
    """Return paths rendered by markdown sections."""

    paths: set[str] = set()
    for section in display_sections(manifest):
        if section.get("kind") == "markdown" and isinstance(section.get("path"), str):
            paths.add(section["path"])
    return paths


def render_audit_section(
    audit_dir: Path,
    manifest: dict[str, Any],
    section: dict[str, Any],
    evidence: Any,
) -> str:
    """Render one experiment audit section."""

    section_id_raw = str(section.get("id") or "section")
    section_id = html.escape(section_id_raw, quote=True)
    title = html.escape(str(section.get("title") or section_id_raw))
    kind = section.get("kind")

    def render_body() -> str:
        if section_id_raw == "timeline" or kind == "timeline":
            return render_timeline_section(audit_dir, section)
        if kind == "markdown":
            return render_markdown_section(audit_dir, section)
        if kind == "evidence":
            return render_evidence_section(
                evidence,
                include_heading=False,
                include_completeness=False,
                section_id=None,
            )
        if kind == "files":
            return render_visible_artifacts(
                evidence, exclude_paths=section_paths(manifest)
            )
        if kind == "json":
            return render_json_section(audit_dir, section)
        if kind == "checks":
            return render_check_list(manifest)
        if kind == "blockers":
            return render_blockers(manifest)
        return '<p class="missing">Section kind is not supported.</p>'

    body = safe_section_html(section_id_raw, render_body)

    panel_class = section_panel_class(section)
    class_attr = f"attempt-panel {panel_class}".strip()
    open_attr = " open" if section_open_by_default(section) else ""
    return (
        f'<details id="{section_id}" class="{html.escape(class_attr, quote=True)}"{open_attr}>'
        f"<summary><h2>{title}</h2></summary>"
        f"{body}"
        "</details>"
    )


def render_check_list(manifest: dict[str, Any]) -> str:
    """Render validation checks from the manifest."""

    checks = manifest.get("checks", [])
    if not isinstance(checks, list) or not checks:
        return "<p>No checks recorded.</p>"

    items: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        title = html.escape(str(check.get("title") or check.get("id") or "Check"))
        status = html.escape(str(check.get("status") or "unknown"))
        command = check.get("command")
        command_html = (
            f" <code>{html.escape(str(command))}</code>"
            if isinstance(command, str) and command
            else ""
        )
        items.append(f"<li><strong>{status}</strong> {title}{command_html}</li>")
    return f"<ul>{''.join(items)}</ul>"


def render_blockers(manifest: dict[str, Any]) -> str:
    """Render blockers from the manifest."""

    blockers = manifest.get("blockers", [])
    if not isinstance(blockers, list) or not blockers:
        return "<p>No blockers recorded.</p>"

    items: list[str] = []
    for blocker in blockers:
        if not isinstance(blocker, dict):
            continue
        reason = html.escape(str(blocker.get("reason") or "Blocker"))
        next_step = html.escape(str(blocker.get("next_step") or ""))
        severity = html.escape(str(blocker.get("severity") or "warning"))
        artifact_id = html.escape(str(blocker.get("artifact_id") or ""))
        items.append(
            f"<li><strong>{severity}</strong> <code>{artifact_id}</code>: "
            f"{reason}<br>Next step: {next_step}</li>"
        )
    return f"<ul>{''.join(items)}</ul>"


def mark_artifact_present(
    audit_dir: Path,
    artifact_id: str,
    path: str | None = None,
) -> dict[str, Any]:
    """Mark an artifact present, optionally updating its path, and drop its blockers."""

    if not ARTIFACT_ID_RE.fullmatch(artifact_id):
        raise ValueError(f"artifact id must be snake_case: {artifact_id!r}")

    manifest = read_audit_manifest(audit_dir)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError(f"{audit_dir / 'audit.json'}: artifacts must be a list")

    target: dict[str, Any] | None = None
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            target = artifact
            break
    if target is None:
        raise ValueError(f"artifact id not found: {artifact_id!r}")

    if path is not None:
        resolved, path_problems = relative_audit_path(
            audit_dir,
            path,
            f"{audit_dir / 'audit.json'}: artifact {artifact_id}",
        )
        if path_problems:
            raise ValueError("; ".join(path_problems))
        target["path"] = path
    else:
        resolved, path_problems = relative_audit_path(
            audit_dir,
            target.get("path"),
            f"{audit_dir / 'audit.json'}: artifact {artifact_id}",
        )
        if path_problems:
            raise ValueError("; ".join(path_problems))

    assert resolved is not None
    if not resolved.is_file():
        raise FileNotFoundError(
            f"{resolved}: file missing; create it before marking present"
        )

    target["status"] = "present"
    blockers = manifest.get("blockers")
    if isinstance(blockers, list):
        manifest["blockers"] = [
            blocker
            for blocker in blockers
            if not (
                isinstance(blocker, dict) and blocker.get("artifact_id") == artifact_id
            )
        ]
    manifest["updated_at"] = utc_timestamp()
    (audit_dir / "audit.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def section_open_by_default(section: dict[str, Any]) -> bool:
    """Return whether a section panel should start expanded."""

    section_id = str(section.get("id") or "")
    kind = str(section.get("kind") or "")
    return section_id in {"report", "blockers"} or kind == "blockers"


def readiness_score_card(manifest: dict[str, Any]) -> str:
    """Render a compact readiness summary for the audit hero."""

    artifacts = manifest.get("artifacts")
    blockers = manifest.get("blockers")
    artifact_rows = (
        [a for a in artifacts if isinstance(a, dict)]
        if isinstance(artifacts, list)
        else []
    )
    required = [a for a in artifact_rows if a.get("required") is True]
    present_required = [a for a in required if a.get("status") == "present"]
    present_all = [a for a in artifact_rows if a.get("status") == "present"]
    blocker_count = len(blockers) if isinstance(blockers, list) else 0
    if required:
        headline = f"{len(present_required)}/{len(required)} required present"
    else:
        headline = f"{len(present_all)} present"
    detail = f"{blocker_count} blocker{'s' if blocker_count != 1 else ''}"
    return (
        '<div class="score-card">'
        '<span class="score-label">Readiness</span>'
        f"<strong>{html.escape(headline)}</strong>"
        f'<span class="score-detail">{html.escape(detail)}</span>'
        "</div>"
    )


def completeness_from_manifest(
    manifest: dict[str, Any],
    evidence: Any,
) -> list[Any]:
    """Build completeness rows from declared manifest artifacts."""

    from psynet.audit.model import CompletenessItem

    items: list[CompletenessItem] = []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return items
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        path = str(artifact.get("path") or "")
        title = str(artifact.get("title") or artifact.get("id") or path)
        status = str(artifact.get("status") or "missing")
        if status == "present":
            present = True
            detail = "present"
        elif status == "not_applicable":
            present = False
            detail = "n/a"
        elif status == "blocked":
            present = False
            detail = "blocked"
        else:
            present = False
            detail = "missing"
        items.append(
            CompletenessItem(
                str(artifact.get("id") or path),
                title if title else path,
                present,
                detail,
            )
        )
    return items


def render_audit_site(
    audit_dir: Path,
    site_dir: Path | None = None,
    *,
    allow_invalid: bool = False,
) -> Path:
    """Render a standalone static experiment audit site.

    By default, validation must pass first. Pass ``allow_invalid=True`` to render
    a structurally broken manifest for debugging.
    """

    if not allow_invalid:
        problems = validate_audit(audit_dir)
        if problems:
            raise AuditValidationError(problems)

    manifest = read_audit_manifest(audit_dir)
    if site_dir is None:
        configured_site = manifest.get("render", {})
        if isinstance(configured_site, dict) and configured_site.get("site_path"):
            resolved_site, site_problems = relative_audit_path(
                audit_dir,
                configured_site.get("site_path"),
                f"{audit_dir / 'audit.json'}: render.site_path",
            )
            if site_problems or resolved_site is None:
                raise ValueError("; ".join(site_problems) or "invalid render.site_path")
            site_dir = resolved_site
        else:
            site_dir = audit_dir / "site"

    site_dir.mkdir(parents=True, exist_ok=True)
    rendered_artifacts = publish_audit_artifacts(audit_dir, site_dir, manifest)

    implementation = manifest.get("implementation", {})
    title = audit_display_title(audit_dir, manifest)
    summary = (
        str(implementation.get("summary"))
        if isinstance(implementation, dict) and implementation.get("summary")
        else ""
    )
    from dataclasses import replace

    evidence = classify_audit_evidence(rendered_artifacts)
    evidence = replace(
        evidence,
        completeness=completeness_from_manifest(manifest, evidence),
    )
    css_url = write_audit_static_assets(site_dir)
    sections = display_sections(manifest)
    experiment = manifest.get("experiment", {})
    environment = manifest.get("environment", {})
    checks = manifest.get("checks", [])
    blockers = manifest.get("blockers", [])
    experiment = experiment if isinstance(experiment, dict) else {}
    environment = environment if isinstance(environment, dict) else {}
    check_count = len(checks) if isinstance(checks, list) else 0
    blocker_count = len(blockers) if isinstance(blockers, list) else 0
    metadata = render_metadata_grid(
        [
            ("Source path", render_metadata_code(experiment.get("source_path"))),
            ("Entry point", render_metadata_code(experiment.get("entry_point"))),
            ("PsyNet version", render_metadata_value(experiment.get("psynet_version"))),
            ("Git commit", render_metadata_code(experiment.get("git_commit"))),
            ("OS", render_metadata_value(environment.get("os"))),
            ("Python", render_metadata_value(environment.get("python_version"))),
            ("Sections", render_metadata_value(len(sections))),
            ("Checks", render_metadata_value(check_count)),
            ("Blockers", render_metadata_value(blocker_count)),
        ],
    )
    section_nav = "".join(
        f'<li><a href="#{html.escape(str(section.get("id")), quote=True)}">'
        f"{html.escape(str(section.get('title') or section.get('id')))}</a></li>"
        for section in sections
    )
    section_panels = "\n".join(
        render_audit_section(audit_dir, manifest, section, evidence)
        for section in sections
    )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{html.escape(css_url)}">
</head>
<body class="attempt-page">
  <article class="prose attempt-detail">
    <header class="attempt-hero">
      <div>
        <p class="eyebrow">Experiment readiness audit</p>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(summary)}</p>
      </div>
      {readiness_score_card(manifest)}
    </header>
    <section class="audit-completeness">
      {render_completeness(evidence)}
    </section>
    {metadata}
    <div class="attempt-layout">
      <aside class="attempt-sidebar" aria-label="Experiment audit sections">
        <nav class="attempt-section-nav">
          <ol>
            {section_nav}
          </ol>
        </nav>
      </aside>
      <div class="attempt-main">
        {section_panels}
      </div>
    </div>
  </article>
  <script>
    document.querySelectorAll("[data-screenshot-gallery]").forEach((gallery) => {{
      const cards = Array.from(gallery.querySelectorAll("[data-screenshot-card]"));
      const panel = gallery.closest(".screenshot-gallery");
      const counter = panel.querySelector("[data-screenshot-counter]");
      const previous = panel.querySelector("[data-screenshot-prev]");
      const next = panel.querySelector("[data-screenshot-next]");
      const caption = panel.querySelector("[data-screenshot-caption]");
      const show = (index) => {{
        cards.forEach((card, cardIndex) => {{ card.hidden = cardIndex !== index; }});
        caption.textContent = cards[index]?.dataset.screenshotCaptionText || "";
        counter.textContent = `${{index + 1}} / ${{cards.length}}`;
        gallery.dataset.screenshotIndex = String(index);
      }};
      const step = (offset) => {{
        const current = Number(gallery.dataset.screenshotIndex || 0);
        show((current + offset + cards.length) % cards.length);
      }};
      if (cards.length > 0) {{
        show(0);
        previous.addEventListener("click", () => step(-1));
        next.addEventListener("click", () => step(1));
      }}
    }});
  </script>
</body>
</html>
"""
    (site_dir / "index.html").write_text(html_text, encoding="utf-8")
    return site_dir


def resolve_audit_site_dir(audit_dir: Path) -> Path:
    """Return the configured rendered-site directory for an audit packet."""

    try:
        manifest = read_audit_manifest(audit_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        return audit_dir / "site"

    configured = manifest.get("render", {})
    if isinstance(configured, dict) and configured.get("site_path"):
        resolved_site, site_problems = relative_audit_path(
            audit_dir,
            configured.get("site_path"),
            f"{audit_dir / 'audit.json'}: render.site_path",
        )
        if site_problems or resolved_site is None:
            raise ValueError("; ".join(site_problems) or "invalid render.site_path")
        return resolved_site
    return audit_dir / "site"


def make_audit_site_server(
    site_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
):
    """Create an HTTP server that serves a rendered audit site directory."""

    import http.server
    from functools import partial

    site_dir = site_dir.resolve()
    if not (site_dir / "index.html").is_file():
        raise FileNotFoundError(
            f"No rendered audit site at {site_dir / 'index.html'}. "
            "Run `psynet audit render` first, or pass `--render`."
        )

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
    return http.server.ThreadingHTTPServer((host, port), handler)


def serve_audit_site(
    site_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Serve a rendered audit site until interrupted."""

    server = make_audit_site_server(site_dir, host=host, port=port)
    bound_host, bound_port = server.server_address[:2]
    display_host = "127.0.0.1" if bound_host in {"0.0.0.0", "::"} else bound_host
    print(f"Serving experiment audit site at http://{display_host}:{bound_port}/")
    print(f"Root: {site_dir.resolve()}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
