"""Minimal experiment that absolutely imports a sibling module."""

import local_helper
import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Local module import"
    helper_value = local_helper.VALUE

    timeline = Timeline(
        InfoPage("Hello", time_estimate=5),
    )
