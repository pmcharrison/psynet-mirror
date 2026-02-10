import json
import os

from psynet.command_line import _write_export_report


def test_write_export_report(tmp_path):
    reports = [{"success": True, "steps": {"test": {"status": "success"}}}]
    report_path = _write_export_report(tmp_path, reports)

    assert os.path.isfile(report_path)
    with open(report_path, "r") as report_file:
        payload = json.load(report_file)

    assert payload["reports"] == reports
