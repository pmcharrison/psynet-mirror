import psynet.experiment
from psynet.demography.gmsi import GMSI
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Demography GMSI (complete) experiment"

    timeline = Timeline(
        GMSI(),
    )
