import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline

from .custom_pages import RandomDigitInputPage


class Exp(psynet.experiment.Experiment):
    label = "Hello world"

    timeline = Timeline(
        NoConsent(),
        RandomDigitInputPage("api_example", time_estimate=5),
        SuccessfulEndPage(),
    )
