# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################


import psynet.experiment
from psynet.asset import DebugStorage
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage, VolumeCalibration
from psynet.prescreen import AntiphaseHeadphoneTest, HugginsHeadphoneTest
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
        HugginsHeadphoneTest(),
        AntiphaseHeadphoneTest(),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.alive_trials) == 12
