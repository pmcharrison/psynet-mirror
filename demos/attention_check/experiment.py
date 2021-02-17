##########################################################################################
# Imports
##########################################################################################

import psynet.experiment
from psynet.demography.general import BasicDemography, Dance, HearingLoss
from psynet.page import SuccessfulEndPage
from psynet.prescreen import AttentionCheck
from psynet.timeline import Timeline

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        BasicDemography(),
        # It is a good practice to add the AttentionCheck in the middle of demographic questions, so its presence is
        # not too obvious
        AttentionCheck(),
        HearingLoss(),
        Dance(),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
