import psynet.experiment
from psynet.demography.general import BasicDemography, Dance, HearingLoss
from psynet.prescreen import AttentionTest
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Attention test demo"

    timeline = Timeline(
        BasicDemography(),
        # It is a good practice to add the AttentionTest in the middle of demographic questions, so its presence is
        # not too obvious
        AttentionTest(),
        HearingLoss(),
        Dance(),
    )
