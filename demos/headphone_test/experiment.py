# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################


import psynet.experiment
from psynet.asset import DebugStorage
from psynet.bot import Bot
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
    label = "Headphone test demo"
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        VolumeCalibration(),
        HeadphoneTest(),
        InfoPage(
            "You passed the headphone screening task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.trials()) == 6
