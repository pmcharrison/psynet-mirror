import time

import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import AsyncCodeBlock, Timeline


def finish_background_work(participant):
    time.sleep(2)
    participant.var.background_work_finished = True


class Exp(psynet.experiment.Experiment):
    label = "Timeline hold lifecycle"

    timeline = Timeline(
        InfoPage("Submit this page to start background feedback processing."),
        AsyncCodeBlock(
            finish_background_work,
            wait=True,
            expected_wait=2,
            check_interval=5,
        ),
        InfoPage("Background feedback processing finished."),
    )
