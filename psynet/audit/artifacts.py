"""Artifact sanitizing and publication helpers for experiment audits."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

HASHED_ARTIFACTS_DIR = "artifacts/blobs/sha256"
MONITOR_STATIC_ARTIFACTS_DIR = "artifacts/monitor-static"
ARTIFACT_URL_PREFIX_ENV = "PSYNET_AUDIT_ARTIFACT_URL_PREFIX"
# Workshop dashboard CI historically used this name; still honored as fallback.
LEGACY_ARTIFACT_URL_PREFIX_ENV = "PSYNETSK_ARTIFACT_URL_PREFIX"
LEGACY_ATTEMPT_ARTIFACTS_DIR = "artifacts/challenges"
MONITOR_STATIC_ROOT = None  # lazy; use monitor_static_root()


def monitor_static_root() -> Path:
    """Return the packaged Dallinger monitor static asset root."""
    from importlib import resources

    return Path(
        resources.files("psynet")
        / "resources"
        / "audit"
        / "monitor-static"
        / "static"
    )


STATIC_REF_RE = re.compile(r'(?:href|src)="/static/(?P<path>[^"]+)"')
CENTRAL_MONITOR_STATIC_REFS = {"vis@4.17.0/dist/vis.min.js"}
CREDENTIAL_REDACTIONS = (
    (re.compile(r"(?i)(dashboard_password=)[^&\"'\s<)]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(dashboard_user=)[^&\"'\s<)]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(Dashboard user:\s*\S+\s+password:\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(Username:\s*`?)[^`\s]+(`?)"), r"\1[REDACTED]\2"),
    (re.compile(r"(?i)(Password:\s*`?)[^`\s]+(`?)"), r"\1[REDACTED]\2"),
    (re.compile(r"(?i)(AWS_ACCESS_KEY_ID\s*=\s*)[^\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(AWS_SECRET_ACCESS_KEY\s*=\s*)[^\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(AWS_SESSION_TOKEN\s*=\s*)[^\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(PROLIFIC_API_TOKEN\s*=\s*)[^\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(PROLIFIC_API_KEY\s*=\s*)[^\s\"']+"), r"\1[REDACTED]"),
)
TEXT_ARTIFACT_EXTENSIONS = {
    ".html",
    ".ipynb",
    ".log",
    ".md",
    ".txt",
    ".json",
    ".csv",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class ArtifactPublication:
    """Publication metadata for a experiment audit artifact."""

    url: str
    published: bool = True
    note: str = ""


def normalized_hashed_artifact_url_prefix(base_url: str | None = None) -> str:
    """Return a URL prefix compatible with old and new preview workflows."""

    if base_url is None:
        base_url = (
            os.environ.get(ARTIFACT_URL_PREFIX_ENV)
            or os.environ.get(LEGACY_ARTIFACT_URL_PREFIX_ENV)
            or HASHED_ARTIFACTS_DIR
        )
    base_url = base_url.rstrip("/")
    old_attempt_suffix = f"/{LEGACY_ATTEMPT_ARTIFACTS_DIR}"
    if base_url.endswith(old_attempt_suffix):
        return base_url[: -len(old_attempt_suffix)] + f"/{HASHED_ARTIFACTS_DIR}"
    return base_url


def hashed_artifact_url(relative_path: str, base_url: str | None = None) -> str:
    """Return the public URL for a content-addressed artifact path."""

    prefix = normalized_hashed_artifact_url_prefix(base_url).rstrip("/")
    return f"{prefix}/{relative_path}"


def redact_known_credentials(text: str) -> str:
    """Redact credential values that should never appear in public artifacts."""

    for pattern, replacement in CREDENTIAL_REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_text_artifact(path: Path) -> None:
    """Redact known credential values from copied text evidence."""

    if path.suffix.lower() not in TEXT_ARTIFACT_EXTENSIONS:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    path.write_text(redact_known_credentials(text), encoding="utf-8")


def sanitize_html_artifact(path: Path) -> None:
    """Make copied HTML evidence safer to view from static previews."""

    html = redact_known_credentials(path.read_text(encoding="utf-8"))
    static_refs = sorted(set(STATIC_REF_RE.findall(html)))
    if "<head>" in html and "<base " not in html:
        html = html.replace("<head>", '<head>\n        <base href="./">', 1)
    html = re.sub(r'href="/dashboard/[^"]*"', 'href="#"', html)
    html = re.sub(r'src="/dashboard/[^"]*"', 'src="#"', html)
    html = html.replace('href="/static/', 'href="./static/')
    html = html.replace('src="/static/', 'src="./static/')
    html = re.sub(r'<script([^>]*)\s*/></script>', r'<script\1></script>', html)
    for ref in CENTRAL_MONITOR_STATIC_REFS:
        html = html.replace(
            f'src="./static/{ref}"',
            f'src="../../../../monitor-static/{ref}"',
        )
        html = html.replace(
            f'href="./static/{ref}"',
            f'href="../../../../monitor-static/{ref}"',
        )
    html = html.replace(
        "</head>",
        """
        <style>
          body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 1rem;
          }
          .container { max-width: none; }
          #dashboard-navigation, #logout { display: none; }
          #monitor-wrapper { display: flex; gap: 1rem; align-items: flex-start; }
          #sidebar { flex: 0 0 18rem; }
          #timeline-wrapper, #timeline, main { flex: 1 1 auto; min-width: 0; }
          table { border-collapse: collapse; width: 100%; }
          th, td {
            border: 1px solid #d0d7de;
            padding: 0.4rem;
            text-align: left;
            vertical-align: top;
          }
          button {
            border: 1px solid #d0d7de;
            border-radius: 0.35rem;
            background: #f6f8fa;
            padding: 0.3rem 0.6rem;
          }
        </style>
    </head>""",
        1,
    )
    path.write_text(html, encoding="utf-8")
    copy_monitor_static_assets(path.parent, static_refs)


def copy_monitor_static_assets(html_dir: Path, static_refs: list[str]) -> None:
    """Copy vendored Dallinger monitor assets next to a copied HTML artifact."""

    for ref in static_refs:
        if ref in CENTRAL_MONITOR_STATIC_REFS:
            continue
        source = monitor_static_root() / ref
        if not source.is_file():
            continue
        destination = html_dir / "static" / ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if ref == "scripts/network-monitor.js":
            disable_live_node_details(destination)


def disable_live_node_details(script_path: Path) -> None:
    """Avoid live dashboard fetches while preserving embedded JSON click details."""

    text = script_path.read_text(encoding="utf-8")
    text = text.replace(
        "$(custom_node).load('/dashboard/node_details/' + "
        "node.options.data.object_type + '/' + String(node.options.data.id));",
        "custom_node.textContent = 'Live dashboard node details are unavailable "
        "in this static snapshot.';",
    )
    script_path.write_text(text, encoding="utf-8")


def write_shared_monitor_static_assets(target_root: Path) -> None:
    """Write monitor static assets shared by all hashed HTML snapshots."""

    for ref in sorted(CENTRAL_MONITOR_STATIC_REFS):
        source = monitor_static_root() / ref
        if not source.is_file():
            continue
        destination = target_root / ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def write_hashed_artifact(
    source_file: Path,
    target_root: Path,
    url_prefix: str | None = None,
) -> str:
    """Sanitize and write one artifact to the content-addressed store."""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / source_file.name
        shutil.copy2(source_file, temp_path)
        if temp_path.suffix.lower() == ".html":
            sanitize_html_artifact(temp_path)
        else:
            sanitize_text_artifact(temp_path)
        digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()
        digest_dir = target_root / digest[:2]

        if temp_path.suffix.lower() == ".html":
            blob_dir = digest_dir / digest
            blob_file = blob_dir / "index.html"
            if not blob_file.exists():
                blob_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(temp_path, blob_file)
                static_dir = temp_path.parent / "static"
                if static_dir.exists():
                    shutil.copytree(
                        static_dir,
                        blob_dir / "static",
                        dirs_exist_ok=True,
                    )
            return hashed_artifact_url(
                f"{digest[:2]}/{digest}/index.html",
                url_prefix,
            )

        blob_file = digest_dir / f"{digest}{temp_path.suffix.lower()}"
        if not blob_file.exists():
            digest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(temp_path, blob_file)
        return hashed_artifact_url(
            blob_file.relative_to(target_root).as_posix(),
            url_prefix,
        )
