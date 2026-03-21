import sys
from pathlib import Path
from subprocess import CalledProcessError

import pytest

DEMO_DIR = Path(__file__).resolve().parents[2] / "demos/experiments/adaptive_test_catr"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

import catr_engine  # noqa: E402


def test_load_item_bank_parses_numeric_parameters(tmp_path):
    item_bank_path = tmp_path / "item_bank.csv"
    item_bank_path.write_text(
        "item_id,a,b,c,d,prompt,choice_1,choice_2,correct_choice\n"
        "item_01,1.2,-0.4,0.2,0.98,Prompt?,A,B,A\n",
        encoding="utf-8",
    )

    rows = catr_engine.load_item_bank(item_bank_path)

    assert len(rows) == 1
    assert rows[0]["item_id"] == "item_01"
    assert rows[0]["a"] == 1.2
    assert rows[0]["b"] == -0.4
    assert rows[0]["c"] == 0.2
    assert rows[0]["d"] == 0.98
    assert rows[0]["correct_choice"] == "A"


def test_start_cat_selects_first_item(monkeypatch):
    def fake_run(item_parameter_matrix, administered_item_indices, responses, theta):
        assert administered_item_indices == []
        assert responses == []
        return {"theta": theta, "sem": None, "next_item_index": 0}

    monkeypatch.setattr(catr_engine, "_run_catr_model", fake_run)

    state = catr_engine.start_cat(item_parameter_matrix=[[1.0, 0.0, 0.2, 0.98]])

    assert state["next_item_index"] == 0
    assert state["done"] is False


def test_register_response_and_advance_stops_on_max_items(monkeypatch):
    def fake_run(item_parameter_matrix, administered_item_indices, responses, theta):
        return {"theta": 0.5, "sem": 0.7, "next_item_index": 1}

    monkeypatch.setattr(catr_engine, "_run_catr_model", fake_run)

    state = catr_engine.initialize_cat_state(item_bank_size=3, max_items=1)
    state["next_item_index"] = 0
    updated_state = catr_engine.register_response_and_advance(
        state=state,
        item_parameter_matrix=[[1.0, 0.0, 0.2, 0.98]] * 3,
        response_correct=1,
    )

    assert updated_state["done"] is True
    assert updated_state["next_item_index"] is None


def test_register_response_and_advance_stops_on_sem_threshold(monkeypatch):
    def fake_run(item_parameter_matrix, administered_item_indices, responses, theta):
        return {"theta": -0.2, "sem": 0.1, "next_item_index": 1}

    monkeypatch.setattr(catr_engine, "_run_catr_model", fake_run)

    state = catr_engine.initialize_cat_state(
        item_bank_size=4,
        max_items=4,
        sem_threshold=0.2,
    )
    state["next_item_index"] = 0
    updated_state = catr_engine.register_response_and_advance(
        state=state,
        item_parameter_matrix=[[1.0, 0.0, 0.2, 0.98]] * 4,
        response_correct=1,
    )

    assert updated_state["done"] is True
    assert updated_state["next_item_index"] is None
    assert updated_state["theta"] == -0.2
    assert updated_state["sem"] == 0.1


def test_register_response_and_advance_continues_when_criteria_not_met(monkeypatch):
    def fake_run(item_parameter_matrix, administered_item_indices, responses, theta):
        return {"theta": 0.3, "sem": 0.8, "next_item_index": 1}

    monkeypatch.setattr(catr_engine, "_run_catr_model", fake_run)

    state = catr_engine.initialize_cat_state(
        item_bank_size=5,
        max_items=5,
        sem_threshold=0.2,
    )
    state["next_item_index"] = 0
    updated_state = catr_engine.register_response_and_advance(
        state=state,
        item_parameter_matrix=[[1.0, 0.0, 0.2, 0.98]] * 5,
        response_correct=0,
    )

    assert updated_state["done"] is False
    assert updated_state["next_item_index"] == 1
    assert updated_state["responses"] == [0]


def test_infer_r_home_error_message_includes_setup_guidance(monkeypatch):
    def raise_file_not_found(command, text):
        raise FileNotFoundError("R missing")

    monkeypatch.setattr(catr_engine.subprocess, "check_output", raise_file_not_found)
    catr_engine.infer_r_home.cache_clear()

    try:
        catr_engine.infer_r_home()
    except RuntimeError as error:
        message = str(error)
    else:
        raise AssertionError("Expected RuntimeError when R executable is missing.")

    assert "catR runtime is not available" in message
    assert "install R and the catR package" in message
    assert "prepare_docker_image.sh" in message


def test_raise_catr_subprocess_error_setup_classification():
    error = CalledProcessError(
        returncode=1,
        cmd=["python", "-c", "script"],
        stderr="Error in library(catR) : there is no package called 'catR'",
    )
    with pytest.raises(RuntimeError) as raised:
        catr_engine._raise_catr_subprocess_error(error)
    message = str(raised.value)
    assert "catR runtime is not available" in message
    assert "install R and the catR package" in message


def test_raise_catr_subprocess_error_runtime_classification():
    error = CalledProcessError(
        returncode=1,
        cmd=["python", "-c", "script"],
        stderr="Error in nextItem(...): unused arguments (itemBank = x)",
    )
    with pytest.raises(RuntimeError) as raised:
        catr_engine._raise_catr_subprocess_error(error)
    message = str(raised.value)
    assert "catR execution failed while processing adaptive-test responses." in message
    assert "missing runtime dependency" in message
