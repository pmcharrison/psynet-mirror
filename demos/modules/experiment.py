# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, Module, PageMaker, Timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def check_module_b(participant):
    assert not participant.locals.has("animal")
    assert participant.locals.color == "blue"
    assert participant.module_states["module_a"][0].var.animal == "cat"

    export = participant.__json__()
    assert export["module_a__animal"] == "cat"
    # second rep would look like: module_a__1__animal


class Exp(psynet.experiment.Experiment):
    label = "Module demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        Module(
            "module_a",
            CodeBlock(lambda participant: participant.locals.set("animal", "cat")),
            PageMaker(
                lambda participant: InfoPage(
                    f"Animal = {participant.locals.animal}",
                ),
                time_estimate=5,
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
            CodeBlock(check_module_b),
        ),
        SuccessfulEndPage(),
    )
