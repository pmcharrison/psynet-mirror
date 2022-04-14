# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################


import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage, VolumeCalibration
from psynet.prescreen import HeadphoneTest
from psynet.timeline import Timeline

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    name = "Headphone test demo"

    timeline = Timeline(
        NoConsent(),
        VolumeCalibration(),
        HeadphoneTest(),
        InfoPage(
            "You passed the headphone screening task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )
