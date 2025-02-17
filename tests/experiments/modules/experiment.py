# pylint: disable=unused-import,abstract-method

import logging

import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, Module, PageMaker, Timeline, for_loop, join

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def check_module_b(participant):
    assert not participant.locals.has("animal")
    assert participant.locals.color == "blue"
    assert participant.module_states["module_a"].var.animal == "cat"

    export = participant.to_dict()
    assert export["module_a__animal"] == "dog"


class Exp(psynet.experiment.Experiment):
    label = "Module demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        Module(
            "module_a",
            for_loop(
                label="module_a_loop",
                iterate_over=lambda: ["cat", "dog"],
                logic=lambda animal: join(
                    CodeBlock(
                        lambda participant: participant.locals.set("animal", animal)
                    ),
                    PageMaker(
                        lambda participant: InfoPage(
                            f"Animal = {participant.locals.animal}",
                        ),
                        time_estimate=5,
                    ),
                ),
                time_estimate_per_iteration=5,
            ),
        ),
        Module(
            "module_b",
            CodeBlock(lambda participant: participant.locals.set("color", "blue")),
            PageMaker(
                lambda participant: InfoPage(
                    f"Color = {participant.locals.color}",
                ),
                time_estimate=5,
            ),
        ),
    )
