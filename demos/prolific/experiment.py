# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.general import BasicDemography
from psynet.page import SuccessfulEndPage
from psynet.prescreen import AttentionTest, HeadphoneTest
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
        HeadphoneTest(),
        BasicDemography(),
        AttentionTest(),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 5
