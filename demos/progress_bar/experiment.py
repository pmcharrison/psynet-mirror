import psynet.experiment
from psynet.modular_page import Bar, ModularPage, Stage
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
            progress_bar=Bar(
                duration=5.0,
                stages=[
                    Stage([0.0, 2.0], "Wait a moment...", color="grey"),
                    Stage([2.0, 3.0], "Red!", color="red"),
                    Stage([3.0, 4.0], "Green!", color="green"),
                    Stage([4.0, 5.0], "Blue!", color="blue"),
                ],
            ),
            time_estimate=15.0,
        ),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
