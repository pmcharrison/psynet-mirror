import csv
import json
import os
import subprocess
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

DEFAULT_START_THETA = 0.0
DEFAULT_MAX_ITEMS = 6
DEFAULT_SEM_THRESHOLD = 0.35
SETUP_ERROR_PATTERNS = (
    "no module named 'rpy2'",
    "there is no package called 'catr'",
    "there is no package called ‘catr’",
    'could not find function "library"',
    "unable to load shared object",
    "fatal error: r home directory is not defined",
)

_CATR_SUBPROCESS_SCRIPT = textwrap.dedent(
    """
    import json
    import math
    import sys

    from rpy2 import robjects
    from rpy2.robjects.vectors import FloatVector, IntVector

    payload = json.loads(sys.stdin.read())
    item_bank = payload["item_bank"]
    theta = float(payload["theta"])
    administered = payload["administered"]
    responses = payload["responses"]

    robjects.r("suppressMessages(library(catR))")
    flat_parameters = [float(value) for row in item_bank for value in row]
    r_item_bank = robjects.r["matrix"](FloatVector(flat_parameters), ncol=4, byrow=True)
    matrix_subset = robjects.r("function(it, idx) it[idx, , drop=FALSE]")

    result = {"theta": theta, "sem": None, "next_item_index": None}

    if administered:
        r_out = IntVector([int(index) + 1 for index in administered])
        r_x = IntVector([int(value) for value in responses])
        r_administered_item_bank = matrix_subset(r_item_bank, r_out)

        theta = float(
            robjects.r["thetaEst"](it=r_administered_item_bank, x=r_x, method="EAP")[0]
        )
        sem = float(
            robjects.r["semTheta"](thEst=theta, it=r_administered_item_bank, x=r_x)[0]
        )
        result["theta"] = theta
        result["sem"] = sem if math.isfinite(sem) else None

        if len(administered) < len(item_bank):
            next_item = robjects.r["nextItem"](
                itemBank=r_item_bank,
                theta=theta,
                out=r_out,
                x=r_x,
                criterion="MFI",
            ).rx2("item")[0]
            result["next_item_index"] = int(next_item) - 1
    else:
        next_item = robjects.r["nextItem"](
            itemBank=r_item_bank,
            theta=theta,
            criterion="MFI",
        ).rx2("item")[0]
        result["next_item_index"] = int(next_item) - 1

    print(json.dumps(result))
    """
)


def _build_runtime_setup_message(problem_details):
    return (
        "catR runtime is not available in this environment.\n"
        f"Details: {problem_details}\n\n"
        "To run this demo locally, install R and the catR package (for example:\n"
        "  sudo apt-get install -y r-base r-base-dev\n"
        '  R -e \'install.packages("catR", repos="https://cloud.r-project.org")\'\n'
        "  uv pip install rpy2\n"
        ").\n"
        "If you use Docker, ensure prepare_docker_image.sh installs R + catR."
    )


def _build_runtime_execution_message(problem_details):
    return (
        "catR execution failed while processing adaptive-test responses.\n"
        "Details: "
        f"{problem_details}\n\n"
        "This often indicates an item-bank or catR call configuration problem "
        "rather than a missing runtime dependency."
    )


def _format_stderr_tail(stderr, max_lines=10):
    stderr = (stderr or "").strip()
    if not stderr:
        return "No stderr."
    return "\n".join(stderr.splitlines()[-max_lines:])


def _looks_like_setup_error(stderr):
    stderr_lower = (stderr or "").lower()
    return any(pattern in stderr_lower for pattern in SETUP_ERROR_PATTERNS)


def _raise_catr_subprocess_error(error):
    stderr_tail = _format_stderr_tail(error.stderr)
    details = (
        "Failed to execute catR via rpy2.\n"
        f"catR subprocess stderr (last lines):\n{stderr_tail}"
    )

    if _looks_like_setup_error(error.stderr):
        raise RuntimeError(_build_runtime_setup_message(details)) from error

    raise RuntimeError(_build_runtime_execution_message(details)) from error


@lru_cache(maxsize=1)
def infer_r_home():
    try:
        r_home = subprocess.check_output(["R", "RHOME"], text=True).strip()
    except FileNotFoundError as error:
        raise RuntimeError(
            _build_runtime_setup_message(
                "Could not execute `R RHOME` because the `R` executable was not found "
                "on PATH."
            )
        ) from error
    except Exception as error:
        raise RuntimeError(
            _build_runtime_setup_message(
                "R_HOME is not set and could not be inferred via `R RHOME`."
            )
        ) from error

    if not r_home:
        raise RuntimeError(
            _build_runtime_setup_message("`R RHOME` returned an empty string.")
        )

    return r_home


def load_item_bank(path):
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(
                {
                    "item_id": row["item_id"],
                    "a": float(row["a"]),
                    "b": float(row["b"]),
                    "c": float(row["c"]),
                    "d": float(row["d"]),
                    "prompt": row["prompt"],
                    "choice_1": row["choice_1"],
                    "choice_2": row["choice_2"],
                    "correct_choice": row["correct_choice"],
                }
            )
    return rows


def build_item_parameter_matrix(item_bank):
    return [[item["a"], item["b"], item["c"], item["d"]] for item in item_bank]


def initialize_cat_state(
    item_bank_size,
    max_items=DEFAULT_MAX_ITEMS,
    sem_threshold=DEFAULT_SEM_THRESHOLD,
    start_theta=DEFAULT_START_THETA,
):
    if item_bank_size <= 0:
        raise ValueError("Item bank must contain at least one item.")

    return {
        "item_bank_size": int(item_bank_size),
        "max_items": int(max_items),
        "sem_threshold": float(sem_threshold),
        "administered_item_indices": [],
        "responses": [],
        "theta": float(start_theta),
        "sem": None,
        "theta_history": [float(start_theta)],
        "sem_history": [None],
        "next_item_index": None,
        "done": False,
    }


def start_cat(
    item_parameter_matrix,
    max_items=DEFAULT_MAX_ITEMS,
    sem_threshold=DEFAULT_SEM_THRESHOLD,
    start_theta=DEFAULT_START_THETA,
):
    state = initialize_cat_state(
        item_bank_size=len(item_parameter_matrix),
        max_items=max_items,
        sem_threshold=sem_threshold,
        start_theta=start_theta,
    )
    initial_step = _run_catr_model(
        item_parameter_matrix=item_parameter_matrix,
        administered_item_indices=[],
        responses=[],
        theta=state["theta"],
    )
    state["next_item_index"] = initial_step["next_item_index"]
    state["done"] = should_stop(state)
    return state


def should_stop(state):
    n_administered = len(state["administered_item_indices"])
    if n_administered >= state["max_items"]:
        return True
    if n_administered >= state["item_bank_size"]:
        return True

    sem = state.get("sem")
    if sem is not None and sem <= state["sem_threshold"]:
        return True

    if state.get("next_item_index") is None:
        return True

    return False


def register_response_and_advance(state, item_parameter_matrix, response_correct):
    if state.get("done"):
        raise ValueError("CAT session is already complete.")
    if state.get("next_item_index") is None:
        raise ValueError("No item is currently selected.")

    state["administered_item_indices"].append(int(state["next_item_index"]))
    state["responses"].append(int(bool(response_correct)))

    step = _run_catr_model(
        item_parameter_matrix=item_parameter_matrix,
        administered_item_indices=state["administered_item_indices"],
        responses=state["responses"],
        theta=state["theta"],
    )
    state["theta"] = float(step["theta"])
    state["sem"] = step["sem"]
    state["theta_history"].append(state["theta"])
    state["sem_history"].append(state["sem"])
    state["next_item_index"] = step["next_item_index"]
    state["done"] = should_stop(state)
    if state["done"]:
        state["next_item_index"] = None

    return state


def _run_catr_model(item_parameter_matrix, administered_item_indices, responses, theta):
    payload = {
        "item_bank": item_parameter_matrix,
        "administered": administered_item_indices,
        "responses": responses,
        "theta": theta,
    }
    env = os.environ.copy()
    env["R_HOME"] = infer_r_home()

    try:
        result = subprocess.run(
            [sys.executable, "-c", _CATR_SUBPROCESS_SCRIPT],
            check=True,
            capture_output=True,
            text=True,
            input=json.dumps(payload),
            env=env,
        )
    except subprocess.CalledProcessError as error:
        _raise_catr_subprocess_error(error)

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("catR subprocess returned an empty response.")

    parsed = json.loads(output.splitlines()[-1])
    return {
        "theta": float(parsed["theta"]),
        "sem": None if parsed["sem"] is None else float(parsed["sem"]),
        "next_item_index": parsed["next_item_index"],
    }
