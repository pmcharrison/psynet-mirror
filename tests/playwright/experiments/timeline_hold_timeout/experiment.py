import psynet.experiment
from psynet.page import InfoPage, wait_while
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Timeline hold timeout"

    timeline = Timeline(
        InfoPage("Start a timeline hold that will time out."),
        wait_while(
            lambda: True,
            expected_wait=1,
            max_wait_time=1,
            check_interval=5,
            fail_on_timeout=False,
        ),
        InfoPage("The timeline hold timed out."),
    )
