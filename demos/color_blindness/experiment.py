# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################


import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import ColorBlindnessTest
from psynet.timeline import Timeline

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        ColorBlindnessTest(),
        InfoPage(
            "You passed the color blindness task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )
