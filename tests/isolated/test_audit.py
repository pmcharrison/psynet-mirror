import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from psynet.audit.cli import (
    init_audit,
    render_audit_section,
    render_audit_site,
    validate_audit,
)
from psynet.command_line import psynet


def run_audit_cli(*args: str):
    """Invoke ``psynet audit`` via Click (the supported CLI)."""

    return CliRunner().invoke(psynet, ["audit", *args], catch_exceptions=False)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def audit_manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "created_at": "2026-06-14T13:00:00Z",
        "updated_at": "2026-06-14T13:00:00Z",
        "profile": "psynet.core",
        "extensions": [],
        "experiment": {
            "source_path": ".",
            "entry_point": "experiment.py",
        },
        "implementation": {
            "summary": "Compare two tones and report which one is higher.",
        },
        "environment": {
            "os": "linux",
        },
        "sections": [
            {
                "id": "plan",
                "title": "Plan",
                "kind": "markdown",
                "path": "PLAN.md",
            },
            {
                "id": "report",
                "title": "Report",
                "kind": "markdown",
                "path": "REPORT.md",
            },
            {
                "id": "evidence",
                "title": "Evidence",
                "kind": "evidence",
            },
            {
                "id": "files",
                "title": "Additional files",
                "kind": "files",
            },
            {
                "id": "checks",
                "title": "Checks",
                "kind": "checks",
            },
            {
                "id": "blockers",
                "title": "Blockers",
                "kind": "blockers",
            },
        ],
        "artifacts": [
            {
                "id": "debug_log",
                "kind": "log",
                "path": "artifacts/psynet_debug.log",
                "title": "Debug log",
                "description": "Command output from a local PsyNet run.",
                "required": False,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "monitor_snapshot",
                "kind": "monitor_snapshot",
                "path": "artifacts/monitor.html",
                "title": "Monitor snapshot",
                "description": "Static monitor snapshot.",
                "required": True,
                "status": "present",
                "created_by": "cli",
            },
            {
                "id": "analysis_notebook",
                "kind": "notebook",
                "path": "analyses/analysis.ipynb",
                "title": "Analysis notebook",
                "description": "Executed analysis notebook.",
                "required": True,
                "status": "blocked",
                "created_by": "agent",
            },
        ],
        "checks": [
            {
                "id": "local_test",
                "title": "PsyNet local test",
                "status": "pass",
                "command": "psynet test local",
            },
        ],
        "blockers": [
            {
                "artifact_id": "analysis_notebook",
                "severity": "warning",
                "reason": "No simulated export has been produced yet.",
                "next_step": "Run psynet simulate and execute the notebook.",
            },
        ],
    }


def write_core_section_files(audit_dir: Path) -> None:
    write(audit_dir / "PLAN.md", "# Plan\n\nUse a chain trial maker.\n")
    write(audit_dir / "REPORT.md", "# Report\n\nReady for review.\n")


def test_render_audit_site_publishes_sanitized_artifacts(tmp_path: Path) -> None:
    audit_dir = tmp_path / "pitch-discrimination-demo" / "audit"
    manifest = audit_manifest()
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(
        audit_dir / "REPORT.md",
        "# Report\n\n"
        "Experiment **behaves** as expected.\n\n"
        "- Functional check passed\n\n"
        "<script>bad()</script>\n",
    )
    write(audit_dir / "PLAN.md", "# Plan\n\nUse a chain trial maker.\n")
    write(
        audit_dir / "artifacts/psynet_debug.log",
        "Dashboard user: admin password: local-password\n",
    )
    write(
        audit_dir / "artifacts/monitor.html",
        '<!doctype html><html><head><link href="/static/css/dashboard.css"></head>'
        '<body><a href="/dashboard/index">Dashboard</a>'
        '<script src="/static/vis@4.17.0/dist/vis.min.js"></script>'
        '<script src="/static/scripts/network-monitor.js"></script></body></html>',
    )

    site_dir = render_audit_site(audit_dir)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="static/css/audit.css">' in index
    assert '<body class="attempt-page">' in index
    assert 'class="attempt-layout"' in index
    assert "Pitch Discrimination Demo" in index
    assert "Experiment readiness audit" in index
    assert "Readiness" in index
    assert "<h1>Report</h1>" not in index
    assert "Experiment <strong>behaves</strong> as expected." in index
    assert "<li>Functional check passed</li>" in index
    assert "<script>bad()</script>" not in index
    assert '<details id="plan" class="attempt-panel plan-panel">' in index
    assert '<details id="report" class="attempt-panel report-panel" open>' in index
    assert "<h1>Plan</h1>" not in index
    assert "Use a chain trial maker." in index
    assert "psynet test local" in index
    assert "No simulated export has been produced yet." in index
    assert index.count('class="attempt-file"') >= 2
    assert (
        '<summary class="file-header"><h3><code>artifacts/psynet_debug.log</code></h3>'
        in index
    )
    assert (
        '<pre class="file-preview"><code>Dashboard user: admin password: [REDACTED]'
        in index
    )
    assert (
        '<summary class="file-header"><h3><code>artifacts/monitor.html</code></h3>'
        in index
    )

    published_files = sorted((site_dir / "static/artifacts/blobs/sha256").glob("**/*"))
    published_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in published_files
        if path.is_file() and path.suffix in {".log", ".html"}
    )
    assert "Dashboard user: admin password: [REDACTED]" in published_text
    assert '<base href="./">' in published_text
    assert "/dashboard/index" not in published_text

    assert (
        site_dir / "static/artifacts/monitor-static/vis@4.17.0/dist/vis.min.js"
    ).exists()
    assert (site_dir / "static/css/audit.css").exists()


def test_render_audit_site_renders_evidence_view(tmp_path: Path) -> None:
    audit_dir = tmp_path / "pitch-discrimination-demo" / "audit"
    manifest = audit_manifest()
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    notebook = artifacts[2]
    assert isinstance(notebook, dict)
    notebook["status"] = "present"
    artifacts.extend(
        [
            {
                "id": "participant_video",
                "kind": "video",
                "path": "artifacts/participant.mp4",
                "title": "Participant walkthrough",
                "description": "Participant video.",
                "required": True,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "screenshots",
                "kind": "screenshot",
                "path": "artifacts/screenshots/01-intro.png",
                "title": "Intro screenshot",
                "description": "Intro screen.",
                "required": False,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "screenshot_second",
                "kind": "screenshot",
                "path": "artifacts/screenshots/02-trial.png",
                "title": "Trial screenshot",
                "description": "Trial screen.",
                "required": False,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "screenshot_manifest",
                "kind": "screenshot",
                "path": "artifacts/screenshots/manifest.json",
                "title": "Screenshot manifest",
                "description": "Screenshot captions.",
                "required": False,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "performance_result",
                "kind": "performance",
                "path": "artifacts/performance.json",
                "title": "Performance",
                "description": "Performance result.",
                "required": True,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "data_export",
                "kind": "data_export",
                "path": "artifacts/data.zip",
                "title": "Data export",
                "description": "Exported data.",
                "required": True,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "simulation_export",
                "kind": "data_export",
                "path": "artifacts/simulated_data.zip",
                "title": "Simulated data",
                "description": "Simulated export.",
                "required": True,
                "status": "present",
                "created_by": "agent",
            },
            {
                "id": "experiment_source",
                "kind": "source",
                "path": "artifacts/source/experiment.py",
                "title": "Experiment source",
                "description": "Main experiment source.",
                "required": False,
                "status": "present",
                "created_by": "agent",
            },
        ]
    )
    manifest["blockers"] = []
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(audit_dir / "PLAN.md", "# Plan\n\nUse a chain trial maker.\n")
    write(audit_dir / "REPORT.md", "# Report\n")
    write(audit_dir / "artifacts/psynet_debug.log", "debug\n")
    write(
        audit_dir / "artifacts/monitor.html", "<html><head></head><body></body></html>"
    )
    write_bytes(audit_dir / "artifacts/participant.mp4", b"video bytes")
    write_bytes(audit_dir / "artifacts/screenshots/01-intro.png", b"png bytes")
    write_bytes(audit_dir / "artifacts/screenshots/02-trial.png", b"png bytes 2")
    write(
        audit_dir / "artifacts/screenshots/manifest.json",
        json.dumps(
            {
                "captions": {
                    "screenshots/01-intro.png": "Intro screen",
                    "screenshots/02-trial.png": "Trial screen",
                }
            }
        ),
    )
    write(
        audit_dir / "artifacts/performance.json",
        json.dumps(
            {
                "results": [
                    {
                        "n_bots": 4,
                        "total_bots_started": 5,
                        "bots_succeeded": 4,
                        "total_requests": 12,
                        "median_response_time": 0.1234,
                        "p95_response_time": 0.4567,
                        "q_delay_p95": 0.0,
                        "request_errors": 1,
                        "bot_errors": 2,
                    }
                ]
            }
        ),
    )
    write_bytes(audit_dir / "artifacts/data.zip", b"data")
    write_bytes(audit_dir / "artifacts/simulated_data.zip", b"simulated")
    write(audit_dir / "artifacts/source/experiment.py", "print('hello')\n")
    write(audit_dir / "analyses/analysis.ipynb", json.dumps({"cells": []}))

    site_dir = render_audit_site(audit_dir)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "<video" in index
    assert "Screenshot walkthrough" in index
    assert "Intro screen" in index
    assert "Trial screen" in index
    assert "data-screenshot-counter>1 / 2</span>" in index
    assert "Performance test result" in index
    assert "<td>4</td>" in index
    assert "<td>3</td>" in index
    assert "Download data export" in index
    assert "simulated_data.zip" in index
    assert "<h3><code>artifacts/data.zip</code></h3>" in index
    assert "Preview is not available." in index
    assert "<h3><code>artifacts/source/experiment.py</code></h3>" in index
    assert '<div class="file-preview code-preview">' in index
    assert "print" in index
    assert "Participant walkthrough <span>present</span>" in index
    assert "Intro screenshot <span>present</span>" in index
    assert "Screenshot manifest <span>present</span>" in index


def test_render_audit_site_renders_timeline_and_json_sections(tmp_path: Path) -> None:
    audit_dir = tmp_path / "pitch-discrimination-demo" / "audit"
    manifest = audit_manifest()
    sections = manifest["sections"]
    assert isinstance(sections, list)
    sections.insert(
        1,
        {
            "id": "timeline",
            "title": "Timeline",
            "kind": "timeline",
            "path": "TIMELINE.md",
        },
    )
    sections.insert(
        2,
        {
            "id": "agent_metadata",
            "title": "Agent metadata",
            "kind": "json",
            "path": "agent.json",
        },
    )
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(audit_dir / "PLAN.md", "# Plan\n\nUse a chain trial maker.\n")
    write(audit_dir / "REPORT.md", "# Report\n\nExperiment works.\n")
    write(
        audit_dir / "TIMELINE.md",
        "# Timeline\n\n"
        "- T+00:00:00 [agent-start] Started.\n"
        "- T+00:02:00 [agent-stop] Finished with **evidence**.\n",
    )
    write(audit_dir / "agent.json", '{"model": "test-model"}\n')
    write(audit_dir / "artifacts/psynet_debug.log", "ok\n")
    write(audit_dir / "artifacts/monitor.html", "<!doctype html><html></html>")

    site_dir = render_audit_site(audit_dir)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert '<details id="timeline" class="attempt-panel">' in index
    assert 'class="timeline-list"' in index
    assert "Finished with <strong>evidence</strong>." in index
    assert '<details id="agent_metadata" class="attempt-panel">' in index
    assert "{&quot;model&quot;: &quot;test-model&quot;}" in index


def test_render_audit_site_polishes_core_section_layout(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["sections"][2]["kind"] = "markdown"  # Legacy packets used this kind.
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(audit_dir / "PLAN.md", "# Plan\n\nBuild a small experiment.\n")
    write(audit_dir / "REPORT.md", "# Report\n\nThe experiment works.\n")
    write(
        audit_dir / "TIMELINE.md",
        "# Timeline\n\n"
        "2026-08-19T12:53:36Z psynet test local passed\n"
        "2026-08-19T12:54:00Z performance-test smoke --audit\n",
    )

    site_dir = render_audit_site(audit_dir)
    index = (site_dir / "index.html").read_text(encoding="utf-8")

    assert "<h1>Plan</h1>" not in index
    assert "<h1>Report</h1>" not in index
    assert '<details id="timeline"' in index
    assert 'class="timeline-list"' in index
    assert "<h1>Timeline</h1>" not in index
    assert "Audit completeness" in index
    assert index.index("Audit completeness") < index.index("Source path")
    assert 'href="#checks"' not in index
    assert '<details id="checks"' not in index


def test_render_audit_site_orders_performance_before_analysis(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    for artifact in manifest["artifacts"]:
        if artifact["id"] in {"performance_result", "analysis_notebook"}:
            artifact["status"] = "present"
    manifest["blockers"] = [
        blocker
        for blocker in manifest["blockers"]
        if blocker["artifact_id"] not in {"performance_result", "analysis_notebook"}
    ]
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(
        audit_dir / "artifacts/performance.json",
        json.dumps({"results": [{"n_bots": 1, "bots_succeeded": 1}]}),
    )
    write(
        audit_dir / "analyses/analysis.ipynb",
        json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {},
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": ["Analysis body"],
                    }
                ],
            }
        ),
    )

    site_dir = render_audit_site(audit_dir)
    index = (site_dir / "index.html").read_text(encoding="utf-8")

    assert index.index('class="performance-result"') < index.index(
        'id="analysis-notebook"'
    )


def test_render_audit_site_publishes_screenshots_from_manifest(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    screenshots = next(
        artifact
        for artifact in manifest["artifacts"]
        if artifact["id"] == "screenshots"
    )
    screenshots["status"] = "present"
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write_bytes(audit_dir / "artifacts/screenshots/01-intro.png", b"png bytes")
    write_bytes(audit_dir / "artifacts/screenshots/02-trial.png", b"png bytes 2")
    write(
        audit_dir / "artifacts/screenshots/manifest.json",
        json.dumps(
            {
                "captions": {
                    "screenshots/01-intro.png": "Intro screen",
                    "screenshots/02-trial.png": "Trial screen",
                }
            }
        ),
    )

    site_dir = render_audit_site(audit_dir)
    index = (site_dir / "index.html").read_text(encoding="utf-8")

    assert "Screenshot walkthrough" in index
    assert "Intro screen" in index
    assert "Trial screen" in index
    assert "data-screenshot-counter>1 / 2</span>" in index


def test_render_audit_section_isolates_render_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_dir = tmp_path / "audit"
    manifest = audit_manifest()
    section = {
        "id": "report",
        "title": "Report",
        "kind": "markdown",
        "path": "REPORT.md",
    }
    write(audit_dir / "REPORT.md", "# Report\n\nWorks.\n")

    def boom_markdown(audit_dir: Path, section: dict[str, object]) -> str:
        raise RuntimeError("markdown render failed")

    monkeypatch.setattr("psynet.audit.cli.render_markdown_section", boom_markdown)

    html = render_audit_section(audit_dir, manifest, section, [])

    assert '<details id="report" class="attempt-panel report-panel" open>' in html
    assert 'class="section-render-error"' in html
    assert "Failed to render section report." in html
    assert "markdown render failed" not in html


def write_valid_review(audit_dir: Path) -> None:
    write(audit_dir / "audit.json", json.dumps(audit_manifest()) + "\n")
    write(audit_dir / "PLAN.md", "# Plan\n\nUse a chain trial maker.\n")
    write(audit_dir / "REPORT.md", "# Report\n\nExperiment behaves as expected.\n")
    write(
        audit_dir / "artifacts/psynet_debug.log",
        "Dashboard user: admin password: local-password\n",
    )
    write(
        audit_dir / "artifacts/monitor.html",
        '<!doctype html><html><head><link href="/static/css/dashboard.css"></head>'
        '<body><a href="/dashboard/index">Dashboard</a>'
        '<script src="/static/vis@4.17.0/dist/vis.min.js"></script>'
        '<script src="/static/scripts/network-monitor.js"></script></body></html>',
    )


def test_validate_audit_accepts_blocked_required_artifact_with_blocker(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "audit"
    write_valid_review(audit_dir)

    assert validate_audit(audit_dir) == []


def test_validate_audit_fails_when_present_artifact_file_is_missing(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "audit"
    write_valid_review(audit_dir)
    (audit_dir / "artifacts/psynet_debug.log").unlink()

    problems = validate_audit(audit_dir)

    assert any(
        "artifact marked present but file is missing" in problem for problem in problems
    )


def test_validate_audit_fails_when_required_artifact_lacks_blocker(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "audit"
    manifest = audit_manifest()
    manifest["blockers"] = []
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(audit_dir / "PLAN.md", "# Plan\n")
    write(audit_dir / "REPORT.md", "# Report\n")
    write(audit_dir / "artifacts/psynet_debug.log", "ok\n")
    write(
        audit_dir / "artifacts/monitor.html", "<html><head></head><body></body></html>"
    )

    problems = validate_audit(audit_dir)

    assert any("required artifact must be present" in problem for problem in problems)


def test_validate_audit_fails_when_markdown_section_path_is_missing(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "audit"
    write(audit_dir / "audit.json", json.dumps(audit_manifest()) + "\n")
    write(audit_dir / "REPORT.md", "# Report\n")
    write(audit_dir / "artifacts/psynet_debug.log", "ok\n")
    write(
        audit_dir / "artifacts/monitor.html", "<html><head></head><body></body></html>"
    )

    problems = validate_audit(audit_dir)

    assert any("section file is missing" in problem for problem in problems)


def test_validate_audit_requires_plan_section_for_core_profile(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    write_valid_review(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["sections"] = [
        section for section in manifest["sections"] if section["id"] != "plan"
    ]
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")

    problems = validate_audit(audit_dir)

    assert any(
        "requires a displayed markdown section" in problem for problem in problems
    )


def test_validate_audit_accepts_unknown_extension_ids_with_warning(
    tmp_path: Path,
) -> None:
    from psynet.audit.cli import collect_audit_warnings

    audit_dir = tmp_path / "audit"
    write_valid_review(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["extensions"] = ["psynetskills.challenge", "example.unknown"]
    manifest["sections"].append(
        {
            "id": "evaluation",
            "title": "Evaluation",
            "kind": "markdown",
            "path": "EVALUATION.md",
        },
    )
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(audit_dir / "EVALUATION.md", "# Evaluation\n\nScore pending.\n")

    assert validate_audit(audit_dir) == []
    warnings = collect_audit_warnings(audit_dir)
    assert not any("psynetskills.challenge" in warning for warning in warnings)
    assert any("example.unknown" in warning for warning in warnings)

    result = run_audit_cli("validate", str(audit_dir))
    assert result.exit_code == 0
    assert "Warning:" in result.stderr
    assert "example.unknown" in result.stderr
    assert "psynetskills.challenge" not in result.stderr
    assert "Audit packet coherent" in result.output


def test_validate_audit_fails_for_invalid_notebook_json(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    manifest = audit_manifest()
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    notebook = artifacts[2]
    assert isinstance(notebook, dict)
    notebook["status"] = "present"
    manifest["blockers"] = []
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")
    write(audit_dir / "PLAN.md", "# Plan\n")
    write(audit_dir / "REPORT.md", "# Report\n")
    write(audit_dir / "artifacts/psynet_debug.log", "ok\n")
    write(
        audit_dir / "artifacts/monitor.html", "<html><head></head><body></body></html>"
    )
    write(audit_dir / "analyses/analysis.ipynb", "{not json")

    problems = validate_audit(audit_dir)

    assert any("invalid notebook JSON" in problem for problem in problems)


def test_validate_audit_cli_exits_nonzero_on_problems(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    write(audit_dir / "audit.json", json.dumps(audit_manifest()) + "\n")

    result = CliRunner().invoke(psynet, ["audit", "validate", str(audit_dir)])

    assert result.exit_code == 1
    combined = f"{result.output}{result.stderr}"
    assert "section file is missing" in combined


def test_init_audit_creates_starter_structure_and_manifest(tmp_path: Path) -> None:
    audit_dir = tmp_path / "pitch-discrimination-demo" / "audit"

    init_audit(audit_dir)

    assert (audit_dir / "audit.json").exists()
    assert (audit_dir / "REPORT.md").exists()
    assert (audit_dir / "PROMPT.md").exists()
    assert (audit_dir / "PLAN.md").exists()
    assert (audit_dir / "TIMELINE.md").exists()
    assert (audit_dir / "artifacts/screenshots").is_dir()
    assert (audit_dir / "analyses").is_dir()
    assert (audit_dir / "logs").is_dir()
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    assert "title" not in manifest["experiment"]
    assert manifest["experiment"]["source_path"] == "."
    assert manifest["profile"] == "psynet.core"
    assert manifest["extensions"] == []
    assert [section["id"] for section in manifest["sections"]] == [
        "prompt",
        "plan",
        "timeline",
        "report",
        "blockers",
        "evidence",
        "files",
        "checks",
    ]
    assert manifest["artifacts"][0]["id"] == "participant_video"
    assert manifest["artifacts"][0]["status"] == "blocked"
    assert manifest["blockers"][0]["severity"] == "error"
    assert {blocker["artifact_id"] for blocker in manifest["blockers"]} == {
        "participant_video",
        "performance_result",
        "monitor_snapshot",
        "simulation_export",
        "analysis_notebook",
    }
    assert validate_audit(audit_dir) == []


def test_init_audit_cli_prints_next_steps(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"

    result = run_audit_cli("init", str(audit_dir), "--source-path", "../experiment")

    assert result.exit_code == 0
    assert "Initialized experiment audit directory" in result.output
    assert "starter packet" in result.output
    assert "psynet audit validate" in result.output
    assert "packet coherent ≠ experiment ready" in result.output
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    assert manifest["experiment"]["source_path"] == "../experiment"


def test_init_audit_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    original = (audit_dir / "audit.json").read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        init_audit(audit_dir)

    assert (audit_dir / "audit.json").read_text(encoding="utf-8") == original


def test_init_audit_force_replaces_starter_files(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    (audit_dir / "audit.json").write_text("custom\n", encoding="utf-8")
    (audit_dir / "REPORT.md").write_text("custom\n", encoding="utf-8")

    init_audit(audit_dir, source_path="..", force=True)

    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    assert manifest["experiment"]["source_path"] == ".."
    assert "Summarize the implementation" in (audit_dir / "REPORT.md").read_text(
        encoding="utf-8",
    )


def test_render_audit_site_uses_resolved_parent_title(tmp_path: Path) -> None:
    audit_dir = tmp_path / "tone-comparison" / "audit"
    init_audit(audit_dir)
    site_dir = render_audit_site(audit_dir)
    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "Tone Comparison" in index
    assert "Experiment readiness audit" in index
    assert "0/5 required present" in index


def test_render_refuses_invalid_manifest_unless_allowed(tmp_path: Path) -> None:
    from psynet.audit.cli import AuditValidationError

    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["artifacts"][0]["status"] = "done"
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")

    with pytest.raises(AuditValidationError) as exc_info:
        render_audit_site(audit_dir)
    assert any(
        "status is not recognized" in problem for problem in exc_info.value.problems
    )
    assert any("allowed:" in problem for problem in exc_info.value.problems)

    site_dir = render_audit_site(audit_dir, allow_invalid=True)
    assert (site_dir / "index.html").is_file()


def test_mark_artifact_present_updates_manifest_and_drops_blocker(
    tmp_path: Path,
) -> None:
    from psynet.audit.cli import mark_artifact_present

    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    write(audit_dir / "artifacts/monitor.html", "<html></html>")

    mark_artifact_present(audit_dir, "monitor_snapshot")

    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    monitor = next(a for a in manifest["artifacts"] if a["id"] == "monitor_snapshot")
    assert monitor["status"] == "present"
    assert all(b["artifact_id"] != "monitor_snapshot" for b in manifest["blockers"])
    assert validate_audit(audit_dir) == []


def test_validate_success_message_mentions_blockers(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)

    result = run_audit_cli("validate", str(audit_dir))

    assert result.exit_code == 0
    assert "Audit packet coherent" in result.output
    assert "blocker" in result.output
    assert "readiness incomplete" in result.output


def test_resolve_audit_dir_autodetects_nested_and_flat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from psynet.audit.cli import resolve_audit_dir

    experiment = tmp_path / "exp"
    nested = experiment / "audit"
    nested.mkdir(parents=True)
    write(nested / "audit.json", "{}\n")
    monkeypatch.chdir(experiment)

    assert resolve_audit_dir(None) == Path("audit")
    assert resolve_audit_dir(Path(".")) == Path("audit")
    assert resolve_audit_dir(Path("audit")) == Path("audit")
    assert resolve_audit_dir(None, for_init=True) == Path("audit")
    assert resolve_audit_dir(Path("."), for_init=True) == Path(".")

    attempt = tmp_path / "attempt"
    attempt.mkdir()
    write(attempt / "audit.json", "{}\n")
    monkeypatch.chdir(attempt)
    assert resolve_audit_dir(None) == Path(".")
    assert resolve_audit_dir(Path(".")) == Path(".")


def test_validate_cli_accepts_experiment_root_dot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment = tmp_path / "exp"
    experiment.mkdir()
    monkeypatch.chdir(experiment)
    result = run_audit_cli("init")
    assert result.exit_code == 0
    assert (experiment / "audit" / "audit.json").is_file()

    result = run_audit_cli("validate", ".")

    assert result.exit_code == 0
    assert "Audit packet coherent" in result.output
    assert "readiness incomplete" in result.output


def test_render_cli_blocked_by_validation(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["artifacts"][0]["status"] = "done"
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")

    result = CliRunner().invoke(psynet, ["audit", "render", str(audit_dir)])

    assert result.exit_code != 0
    combined = f"{result.output}{result.stderr}"
    assert "Render blocked by validation errors" in combined


def test_validate_rejects_escaping_render_site_path(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["render"] = {
        "site_path": "../../outside-site",
        "generator": "psynet audit",
    }
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")

    problems = validate_audit(audit_dir)
    assert any("render.site_path" in problem for problem in problems)
    assert any("must stay inside" in problem for problem in problems)


def test_render_refuses_escaping_site_path_even_with_allow_invalid(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    manifest = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    manifest["render"] = {
        "site_path": "../../outside-site",
        "generator": "psynet audit",
    }
    write(audit_dir / "audit.json", json.dumps(manifest) + "\n")

    with pytest.raises(ValueError, match="render.site_path|must stay inside"):
        render_audit_site(audit_dir, allow_invalid=True)
    assert not (tmp_path / "outside-site").exists()


def test_make_audit_site_server_serves_index(tmp_path: Path) -> None:
    import threading
    import urllib.request

    from psynet.audit.cli import make_audit_site_server

    site_dir = tmp_path / "site"
    write(site_dir / "index.html", "<!doctype html><title>audit</title>hello-audit")

    server = make_audit_site_server(site_dir, host="127.0.0.1", port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            assert response.status == 200
            body = response.read()
        assert b"hello-audit" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_make_audit_site_server_requires_index(tmp_path: Path) -> None:
    from psynet.audit.cli import make_audit_site_server

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="psynet audit render"):
        make_audit_site_server(site_dir, host="127.0.0.1", port=0)


def test_audit_serve_cli_errors_when_site_missing(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)

    result = CliRunner().invoke(
        psynet, ["audit", "serve", str(audit_dir), "--port", "0"]
    )

    assert result.exit_code != 0
    combined = f"{result.output}{result.stderr}"
    assert "No rendered audit site" in combined
    assert "psynet audit render" in combined


def test_audit_serve_cli_allow_invalid_requires_render() -> None:
    result = CliRunner().invoke(psynet, ["audit", "serve", "--allow-invalid"])

    assert result.exit_code != 0
    combined = f"{result.output}{result.stderr}"
    assert "--allow-invalid is only valid together with --render" in combined


def test_audit_serve_cli_render_then_serve(tmp_path: Path, monkeypatch) -> None:
    from psynet.audit import cli as audit_cli

    audit_dir = tmp_path / "audit"
    init_audit(audit_dir)
    # Provide enough present artifacts for validate/render if needed via allow_invalid
    calls = []

    def fake_serve(site_dir, *, host="127.0.0.1", port=8765):
        calls.append((Path(site_dir), host, port))
        assert (Path(site_dir) / "index.html").is_file()

    monkeypatch.setattr(audit_cli, "serve_audit_site", fake_serve)

    result = CliRunner().invoke(
        psynet,
        [
            "audit",
            "serve",
            str(audit_dir),
            "--render",
            "--allow-invalid",
            "--host",
            "127.0.0.1",
            "--port",
            "9123",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Rendered experiment audit site" in result.output
    assert calls == [(audit_dir / "site", "127.0.0.1", 9123)]
