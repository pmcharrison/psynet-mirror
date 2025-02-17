import psynet.experiment
from psynet.modular_page import ModularPage
from psynet.page import InfoPage
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Progress display demo"

    consent_audiovisual_recordings = False

    timeline = Timeline(
        ModularPage(
            "progress_bar_demo",
            "Check out this progress bar!",
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(0.75, "Wait a moment...", color="grey"),
                    ProgressStage(1, "Red!", color="red"),
                    ProgressStage(1, "Green!", color="green"),
                    ProgressStage(1, "Blue!", color="blue"),
                ],
            ),
            time_estimate=15.0,
        ),
        ModularPage(
            "progress_bar_demo",
            "Here we hide the progress bar.",
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage([0.0, 1.0], "Wait a moment...", color="grey"),
                    ProgressStage([1.0, 2.0], "Red!", color="red"),
                    ProgressStage([2.0, 3.0], "Green!", color="green"),
                    ProgressStage([3.0, 4.0], "Blue!", color="blue"),
                ],
                show_bar=False,
            ),
            time_estimate=15.0,
        ),
        InfoPage(
            """"
            Alternatively, one can define messages via event registration. This approach can be more flexible,
            allowing you for example to incorporate arbitrary Javascript.
            """,
            time_estimate=5,
            events={
                "customEvent1": Event(
                    is_triggered_by="trialStart", delay=0.0, message="Three, "
                ),
                "customEvent2": Event(
                    is_triggered_by="trialStart", delay=1.0, message="two, "
                ),
                "customEvent3": Event(
                    is_triggered_by="trialStart",
                    delay=2.0,
                    message="one... ",
                    message_color="red",
                ),
                "customEvent4": Event(
                    is_triggered_by="trialStart", delay=3.0, js="alert('Boo!')"
                ),
            },
        ),
    )
