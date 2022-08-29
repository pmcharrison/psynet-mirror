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
    assert not participant.var.has("animal")
    assert participant.var.color == "blue"
    assert participant.modules["module_a"].var.animal == "cat"


class Exp(psynet.experiment.Experiment):
    label = "Module demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        Module(
            "module_a",
            CodeBlock(lambda participant: participant.var.set("animal", "cat")),
            PageMaker(
                lambda participant: InfoPage(
                    f"Animal = {participant.var.animal}",
                ),
                time_estimate=5,
            ),
        ),
        Module(
            "module_b",
            CodeBlock(lambda participant: participant.var.set("color", "blue")),
            PageMaker(
                lambda participant: InfoPage(
                    f"Color = {participant.var.color}",
                ),
                time_estimate=5,
            ),
            CodeBlock(check_module_b),
        ),
        SuccessfulEndPage(),
    )
