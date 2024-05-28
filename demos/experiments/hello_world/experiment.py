import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Hello world"

    timeline = Timeline(
        NoConsent(),
        InfoPage("Hello world!", time_estimate=5),
        SuccessfulEndPage(),
    )
