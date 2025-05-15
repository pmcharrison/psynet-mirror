import psynet.experiment
from psynet.demography.general import (
    BasicDemography,
    BasicMusic,
    Dance,
    ExperimentFeedback,
    HearingLoss,
    Income,
    Language,
    LanguagesInOrderOfProficiency,
    MotherTongues,
    SpeechDisorders,
)
from psynet.demography.gmsi import GMSI
from psynet.demography.pei import PEI
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Demography demo"

    timeline = Timeline(
        BasicDemography(),
        Language(),
        MotherTongues(),
        LanguagesInOrderOfProficiency(),
        BasicMusic(),
        HearingLoss(),
        Dance(),
        SpeechDisorders(),
        Income(),
        ExperimentFeedback(),
        GMSI(),
        PEI(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
