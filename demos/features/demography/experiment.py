import psynet.experiment
from psynet.consent import NoConsent
from psynet.demography.general import (
    BasicDemography,
    BasicMusic,
    Dance,
    ExperimentFeedback,
    HearingLoss,
    Income,
    Language,
    SpeechDisorders,
)
from psynet.demography.gmsi import GMSI
from psynet.demography.pei import PEI
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Demography demo"

    timeline = Timeline(
        NoConsent(),
        BasicDemography(),
        Language(),
        BasicMusic(),
        HearingLoss(),
        Dance(),
        SpeechDisorders(),
        Income(),
        ExperimentFeedback(),
        GMSI(),
        PEI(),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
