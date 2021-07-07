##########################################################################################
# Imports
##########################################################################################

import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.general import BasicDemography, Dance, HearingLoss
from psynet.page import SuccessfulEndPage
from psynet.prescreen import AttentionTest
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
        BasicDemography(),
        # It is a good practice to add the AttentionTest in the middle of demographic questions, so its presence is
        # not too obvious
        AttentionTest(),
        HearingLoss(),
        Dance(),
        SuccessfulEndPage(),
    )
