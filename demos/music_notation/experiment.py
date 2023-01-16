# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, MusicNotationPrompt
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class Exp(psynet.experiment.Experiment):
    label = "Music notation demo"

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "example_1",
            MusicNotationPrompt(
                content="[E2B2]",
                text="Here's some music notation:",
            ),
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )
