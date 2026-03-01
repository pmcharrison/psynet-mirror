import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from psynet.command_line import run_export


def _fake_export_vars(deployment_id="test-deployment", label="test-label"):
    return {"deployment_id": deployment_id, "label": label}


def test_export_local_continues_on_step_failures(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    ctx = SimpleNamespace(
        invoke=lambda *args, **kwargs: _fake_export_vars(),
    )

    config = SimpleNamespace(ready=True, load=lambda: None, get=lambda _: "value")
    experiment_class = SimpleNamespace(label="test-label")
    with (
        patch(
            "psynet.experiment.import_local_experiment",
            return_value={"class": experiment_class},
        ),
        patch("psynet.command_line.get_config", return_value=config),
        patch("psynet.command_line.export_database", side_effect=RuntimeError("db")),
        patch("psynet.command_line.export_assets", side_effect=RuntimeError("assets")),
        patch(
            "psynet.command_line._export_source_code", side_effect=RuntimeError("src")
        ),
        patch("psynet.command_line.export_logs", side_effect=RuntimeError("logs")),
        patch("psynet.command_line.postprocess_database_zip_to_csv"),
    ):
        run_export(
            ctx,
            exp_variables=_fake_export_vars(),
            local=True,
            path=str(export_dir),
            postprocess_location="local",
            postprocess_method="csv",
            assets="all",
            anonymize="no",
        )

    report_path = export_dir / "export_report.json"
    assert report_path.exists()
    with open(report_path, "r") as report_file:
        payload = json.load(report_file)

    report = payload["reports"][0]
    assert report["success"] is False
    assert report["steps"]["database_export"]["status"] == "failed"
    assert report["steps"]["postprocess_data"]["status"] == "skipped"
    assert report["steps"]["assets_export"]["status"] == "failed"
    assert report["steps"]["source_code_export"]["status"] == "failed"
    assert report["steps"]["logs_export"]["status"] == "skipped"


def test_export_remote_records_dashboard_failure(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    ctx = SimpleNamespace(
        invoke=lambda *args, **kwargs: _fake_export_vars(),
    )
    response = Mock()
    response.status_code = 500
    response.reason = "Internal Server Error"
    response.json.side_effect = json.JSONDecodeError("bad", "doc", 0)
    response.content = b"error"

    config = SimpleNamespace(ready=True, load=lambda: None, get=lambda _: "value")
    experiment_class = SimpleNamespace(label="test-label")
    with (
        patch(
            "psynet.experiment.import_local_experiment",
            return_value={"class": experiment_class},
        ),
        patch("psynet.command_line.get_config", return_value=config),
        patch("psynet.command_line.get_experiment_url", return_value="http://test"),
        patch("psynet.command_line.requests.get", return_value=response),
    ):
        run_export(
            ctx,
            exp_variables=_fake_export_vars(),
            app="test-app",
            local=False,
            path=str(export_dir),
            postprocess_location="remote",
            postprocess_method="csv",
            assets="none",
            anonymize="no",
        )

    report_path = export_dir / "export_report.json"
    assert report_path.exists()
    with open(report_path, "r") as report_file:
        payload = json.load(report_file)

    report = payload["reports"][0]
    assert report["success"] is False
    assert report["steps"]["dashboard_export"]["status"] == "failed"


def test_export_local_records_postprocess_diagnostics(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    ctx = SimpleNamespace(
        invoke=lambda *args, **kwargs: _fake_export_vars(),
    )

    config = SimpleNamespace(ready=True, load=lambda: None, get=lambda _: "value")
    experiment_class = SimpleNamespace(label="test-label")
    diagnostics = {
        "decode_failures": {
            "count": 2,
            "examples": [
                {
                    "table": "participant",
                    "field": "vars",
                    "error_type": "ValueError",
                    "error": "bad payload",
                }
            ],
        }
    }
    with (
        patch(
            "psynet.experiment.import_local_experiment",
            return_value={"class": experiment_class},
        ),
        patch("psynet.command_line.get_config", return_value=config),
        patch("psynet.command_line.export_database", return_value="database.zip"),
        patch("psynet.command_line.postprocess_export_data", return_value=diagnostics),
        patch("psynet.command_line.export_assets", return_value=True),
        patch("psynet.command_line._export_source_code", return_value=True),
        patch("psynet.command_line.export_logs", return_value=True),
    ):
        run_export(
            ctx,
            exp_variables=_fake_export_vars(),
            local=True,
            path=str(export_dir),
            postprocess_location="local",
            postprocess_method="csv",
            assets="none",
            anonymize="no",
        )

    report_path = export_dir / "export_report.json"
    with open(report_path, "r") as report_file:
        payload = json.load(report_file)

    report = payload["reports"][0]
    step = report["steps"]["postprocess_data"]
    assert step["status"] == "success"
    assert step["details"]["decode_failures"]["count"] == 2
