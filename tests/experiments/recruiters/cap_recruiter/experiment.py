# pylint: disable=unused-import,abstract-method,unused-argument

import psynet.experiment
from psynet.consent import MainConsent
from psynet.page import InfoPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "CAP recruiter demo"

    timeline = Timeline(
        MainConsent(),
        InfoPage("You finished the experiment!", time_estimate=0),
    )
