# pylint: disable=unused-import,abstract-method

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage
from psynet.prescreen import AttentionTest
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Prolific demo"

    timeline = Timeline(
        NoConsent(),
        AttentionTest(),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 5
