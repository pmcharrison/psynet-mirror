from pathlib import Path

from psynet.audit.artifacts import (
    HASHED_ARTIFACTS_DIR,
    sanitize_html_artifact,
    write_hashed_artifact,
)


def test_write_hashed_artifact_redacts_text_and_normalizes_legacy_prefix(
    tmp_path: Path,
) -> None:
    source = tmp_path / "psynet_debug.log"
    source.write_text(
        "Dashboard user: admin password: local-password\n"
        "AWS_SECRET_ACCESS_KEY=secret\n",
        encoding="utf-8",
    )
    target_root = tmp_path / HASHED_ARTIFACTS_DIR

    url = write_hashed_artifact(
        source,
        target_root,
        "https://example.test/artifacts/challenges",
    )

    prefix = f"https://example.test/{HASHED_ARTIFACTS_DIR}/"
    assert url.startswith(prefix)
    exported = target_root / url.removeprefix(prefix)
    assert exported.exists()
    assert exported.read_text(encoding="utf-8") == (
        "Dashboard user: admin password: [REDACTED]\n"
        "AWS_SECRET_ACCESS_KEY=[REDACTED]\n"
    )


def test_sanitize_html_artifact_rewrites_monitor_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "monitor.html"
    source.write_text(
        '<!doctype html><html><head><link href="/static/css/dashboard.css"></head>'
        '<body><a href="/dashboard/index">Dashboard</a>'
        '<script src="/static/vis@4.17.0/dist/vis.min.js"></script>'
        '<script src="/static/scripts/network-monitor.js"></script></body></html>',
        encoding="utf-8",
    )

    sanitize_html_artifact(source)

    html = source.read_text(encoding="utf-8")
    assert '<base href="./">' in html
    assert 'href="./static/css/dashboard.css"' in html
    assert 'href="#"' in html
    assert 'src="../../../../monitor-static/vis@4.17.0/dist/vis.min.js"' in html

    network_monitor = tmp_path / "static/scripts/network-monitor.js"
    assert network_monitor.exists()
    assert "Live dashboard node details are unavailable" in network_monitor.read_text(
        encoding="utf-8",
    )
