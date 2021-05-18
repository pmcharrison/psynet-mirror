import psynet.experiment
from psynet.modular_page import ModularPage, ProgressDisplay, ProgressStage
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        ModularPage(
            "progress_bar_demo",
            "Check out this progress bar!",
            progress_display=ProgressDisplay(
                duration=5.0,
                stages=[
                    ProgressStage([0.0, 1.0], "Wait a moment...", color="grey"),
                    ProgressStage([1.0, 2.0], "Red!", color="red"),
                    ProgressStage([2.0, 3.0], "Green!", color="green"),
                    ProgressStage([3.0, 4.0], "Blue!", color="blue"),
                ],
            ),
            time_estimate=15.0,
        ),
        ModularPage(
            "progress_bar_demo",
            "Here we hide the progress bar.",
            progress_display=ProgressDisplay(
                duration=5.0,
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
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
