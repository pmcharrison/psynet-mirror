import psynet.experiment
from psynet.timeline import Timeline

from .custom_pages import RandomDigitInputPage


class Exp(psynet.experiment.Experiment):
    label = "Hello world"

    timeline = Timeline(
        RandomDigitInputPage("api_example", time_estimate=5),
    )
