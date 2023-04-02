import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.gmsi import GMSI
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "GMSI (short) demo"

    timeline = Timeline(
        NoConsent(),
        GMSI(short_version=True),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
