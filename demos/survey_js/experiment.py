# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, SurveyJSControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class Exp(psynet.experiment.Experiment):
    label = "SurveyJS demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "example_1",
            "Here's a simple SurveyJS example.",
            SurveyJSControl(
                json={},
            ),
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )
