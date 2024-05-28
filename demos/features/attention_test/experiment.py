import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.general import BasicDemography, Dance, HearingLoss
from psynet.page import SuccessfulEndPage
from psynet.prescreen import AttentionTest
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Attention test demo"

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
