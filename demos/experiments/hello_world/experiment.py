import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Hello world"

    timeline = Timeline(
        InfoPage("Hello world!", time_estimate=5),
    )
