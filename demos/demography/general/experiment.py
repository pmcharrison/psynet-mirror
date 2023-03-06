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
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "Demography (general) demo"

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
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
