# pylint: disable=unused-import,abstract-method

import logging

import psynet.experiment
from psynet.equipment import MonitorInformation
from psynet.page import DebugResponsePage, InfoPage
from psynet.timeline import Timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class Exp(psynet.experiment.Experiment):
    label = "Monitor information demo"

    timeline = Timeline(
        InfoPage(
            """
The next page records information about the participant's monitor.
This is useful for experiments that rely on graphics.
""",
            time_estimate=5,
        ),
        MonitorInformation(),
        DebugResponsePage(),
    )
