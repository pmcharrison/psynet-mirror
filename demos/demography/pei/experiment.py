import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.pei import PEI
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "PEI demo"

    timeline = Timeline(
        NoConsent(),
        PEI(),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
