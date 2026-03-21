from pathlib import Path

import psynet.experiment
from psynet.modular_page import ModularPage, Prompt, PushButtonControl
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, PageMaker, Timeline, while_loop

try:
    from .catr_engine import (
        build_item_parameter_matrix,
        load_item_bank,
        register_response_and_advance,
        start_cat,
    )
except ImportError:
    from catr_engine import (
        build_item_parameter_matrix,
        load_item_bank,
        register_response_and_advance,
        start_cat,
    )

# This demo implements a simple computerised adaptive test (CAT) using catR.
#
# The adaptive loop follows a standard pattern:
# - choose an item with catR (MFI criterion),
# - present the item on a PsyNet page,
# - score the response,
# - re-estimate theta with catR (EAP),
# - stop when max items is reached or SEM falls below threshold.
#
# How to customize this demo for your own application:
# - Replace item_bank.csv with your calibrated item parameters and item content.
# - Modify question rendering to use richer stimuli (audio, images, text passage, etc.).
# - Tune CAT settings (selection criterion, estimation method, stop rule) in catr_engine.py.
# - Replace the demo scoring logic with domain-specific scoring as needed.

ITEM_BANK_PATH = Path(__file__).with_name("item_bank.csv")
ITEM_BANK = load_item_bank(ITEM_BANK_PATH)
ITEM_PARAMETER_MATRIX = build_item_parameter_matrix(ITEM_BANK)

MAX_ITEMS = 6
SEM_THRESHOLD = 0.35
START_THETA = 0.0


def initialize_adaptive_session(participant):
    participant.var.set(
        "cat_state",
        start_cat(
            item_parameter_matrix=ITEM_PARAMETER_MATRIX,
            max_items=MAX_ITEMS,
            sem_threshold=SEM_THRESHOLD,
            start_theta=START_THETA,
        ),
    )


def _current_item(participant):
    state = participant.var.cat_state
    if state["next_item_index"] is None:
        raise RuntimeError("No adaptive-test item is currently selected.")
    return ITEM_BANK[state["next_item_index"]]


def make_adaptive_question_page(participant):
    state = participant.var.cat_state
    item = _current_item(participant)
    item_number = len(state["administered_item_indices"]) + 1
    return ModularPage(
        "adaptive_item",
        Prompt(f"Item {item_number}: {item['prompt']}"),
        PushButtonControl(
            choices=[item["choice_1"], item["choice_2"]],
            arrange_vertically=False,
            bot_response=lambda bot, item=item: item["correct_choice"],
        ),
        time_estimate=6,
    )


def score_response_and_advance(participant):
    item = _current_item(participant)
    response_correct = int(participant.answer == item["correct_choice"])
    state = participant.var.cat_state
    updated_state = register_response_and_advance(
        state=state,
        item_parameter_matrix=ITEM_PARAMETER_MATRIX,
        response_correct=response_correct,
    )
    participant.var.set("cat_state", updated_state)


def make_summary_page(participant):
    state = participant.var.cat_state
    n_items = len(state["responses"])
    n_correct = sum(state["responses"])
    accuracy = n_correct / n_items if n_items else 0.0
    sem_text = "N/A" if state["sem"] is None else f"{state['sem']:.3f}"
    return InfoPage(
        (
            "Adaptive test complete.\n\n"
            f"Administered items: {n_items}\n"
            f"Correct responses: {n_correct}\n"
            f"Accuracy: {accuracy:.1%}\n"
            f"Final theta (EAP): {state['theta']:.3f}\n"
            f"Final SEM: {sem_text}"
        ),
        time_estimate=5,
    )


class Exp(psynet.experiment.Experiment):
    label = "Adaptive testing with catR"

    timeline = Timeline(
        InfoPage(
            (
                "This demo runs a computerised adaptive test with catR.\n"
                "You will answer a sequence of two-option items, where the next "
                "item is selected based on your previous responses."
            ),
            time_estimate=5,
        ),
        CodeBlock(initialize_adaptive_session),
        while_loop(
            "adaptive_test_loop",
            lambda participant: not participant.var.cat_state["done"],
            [
                PageMaker(make_adaptive_question_page, time_estimate=6),
                CodeBlock(score_response_and_advance),
            ],
            expected_repetitions=MAX_ITEMS,
        ),
        PageMaker(make_summary_page, time_estimate=5),
        InfoPage(
            "Thanks for trying the adaptive test demo.",
            time_estimate=5,
        ),
    )
