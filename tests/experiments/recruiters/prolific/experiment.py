# pylint: disable=unused-import,abstract-method

import psynet.experiment
from psynet.prescreen import AttentionTest
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Prolific demo"

    timeline = Timeline(
        AttentionTest(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 5
