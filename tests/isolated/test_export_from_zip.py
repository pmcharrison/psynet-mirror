import csv
import zipfile
from pathlib import Path

import pandas as pd

from psynet.data import postprocess_database_zip_to_csv
from psynet.serialize import serialize, unserialize


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _make_database_zip(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    participant_rows = [
        {
            "id": 1,
            "type": "psynet.participant.Participant",
            "worker_id": "worker-1",
            "vars": serialize({"age": 30, "_internal": "skip"}),
            "module_id": "alpha",
            "started_modules": serialize(["alpha"]),
            "finished_modules": serialize([]),
            "aborted_modules": serialize([]),
        }
    ]
    _write_csv(data_dir / "participant.csv", participant_rows)

    module_state_rows = [
        {
            "id": 1,
            "type": "psynet.timeline.ModuleState",
            "participant_id": 1,
            "module_id": "alpha",
            "time_started": "2024-01-01 00:00:01",
            "vars": serialize({"score": 1, "_private": "hidden"}),
        },
        {
            "id": 2,
            "type": "psynet.timeline.ModuleState",
            "participant_id": 1,
            "module_id": "alpha",
            "time_started": "2024-01-01 00:00:02",
            "vars": serialize({"score": 2}),
        },
        {
            "id": 3,
            "type": "psynet.timeline.ModuleState",
            "participant_id": 1,
            "module_id": "beta",
            "time_started": "2024-01-01 00:00:03",
            "vars": serialize({"level": 5}),
        },
    ]
    _write_csv(data_dir / "module_state.csv", module_state_rows)

    trial_definition = {
        "vector": [1, 2, 3],
        "initial_index": 0,
        "active_index": 1,
    }
    trial_answer = {"choice": 2}
    info_rows = [
        {
            "id": 10,
            "type": "psynet.trial.gibbs.GibbsTrial",
            "participant_id": 1,
            "definition": serialize(trial_definition),
            "answer": serialize(trial_answer),
            "vars": serialize({"trial_var": "alpha"}),
        }
    ]
    _write_csv(data_dir / "info.csv", info_rows)

    response_rows = [
        {
            "id": 20,
            "type": "psynet.timeline.Response",
            "participant_id": 1,
            "question": "q1",
            "answer": serialize({"value": "ok"}),
            "client_ip_address": "127.0.0.1",
        }
    ]
    _write_csv(data_dir / "response.csv", response_rows)

    zip_path = tmp_path / "database.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for csv_path in data_dir.iterdir():
            archive.write(csv_path, arcname=f"data/{csv_path.name}")
    return zip_path


def test_postprocess_database_zip_unpacks_and_scrubs(tmp_path: Path) -> None:
    zip_path = _make_database_zip(tmp_path)
    output_dir = tmp_path / "export"

    diagnostics = postprocess_database_zip_to_csv(
        zip_path,
        output_dir,
        scrub_pii=True,
        export_classes_to_skip=[],
    )
    assert diagnostics["decode_failures"]["count"] == 0

    participants = pd.read_csv(output_dir / "Participant.csv")
    assert "worker_id" not in participants.columns
    assert "age" in participants.columns
    assert "_internal" not in participants.columns
    assert participants["age"].iloc[0] == 30
    assert participants["module_id"].iloc[0] == "alpha"
    assert participants["alpha__score"].iloc[0] == 1
    assert participants["alpha__1__score"].iloc[0] == 2
    assert participants["beta__level"].iloc[0] == 5

    trials = pd.read_csv(output_dir / "GibbsTrial.csv")
    assert "trial_var" in trials.columns
    assert trials["trial_var"].iloc[0] == "alpha"
    assert unserialize(trials["definition"].iloc[0])["vector"] == [1, 2, 3]
    assert unserialize(trials["vector"].iloc[0]) == [1, 2, 3]
    assert int(trials["initial_index"].iloc[0]) == 0
    assert int(trials["active_index"].iloc[0]) == 1
    assert unserialize(trials["answer"].iloc[0]) == {"choice": 2}
    assert int(trials["choice"].iloc[0]) == 2

    responses = pd.read_csv(output_dir / "Response.csv")
    assert "client_ip_address" not in responses.columns
