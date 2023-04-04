# pylint: disable=unused-import,abstract-method,unused-argument

import psynet.experiment
from psynet.consent import MainConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "CAP recruiter demo"

    timeline = Timeline(
        MainConsent(),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = (
            1  # increase to simulate multiple participants at once
        )
