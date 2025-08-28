import psynet.experiment
from psynet.demography.gmsi import GMSI
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Demography GMSI (two modules with subscales) experiment"

    timeline = Timeline(
        GMSI(label="gmsi_1", subscales=["Singing Abilities"]),
        GMSI(label="gmsi_2", subscales=["Musical Training"]),
    )
