import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.gmsi import GMSI
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Demography GMSI (two modules with subscales) experiment"

    timeline = Timeline(
        NoConsent(),
        GMSI(label="gmsi_1", subscales=["Singing Abilities"]),
        GMSI(label="gmsi_2", subscales=["Musical Training"]),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
