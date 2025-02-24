import psynet.experiment
from psynet.demography.gmsi import GMSI
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "GMSI (short) experiment"

    timeline = Timeline(
        GMSI(short_version=True),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
