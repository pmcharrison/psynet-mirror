from datetime import datetime

from dallinger.experiment import experiment_route

import psynet.experiment
from psynet.consent import CAPRecruiterStandardConsent
from psynet.modular_page import ModularPage, TextControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Module, PageMaker, Timeline
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    variables = {
        "show_abort_button": True,
        "min_accumulated_bonus_for_abort": 0.10,
    }

    @experiment_route("/custom_route", methods=["POST", "GET"])
    @classmethod
    def custom_route(cls):
        return f"A custom route for {cls.__name__}."

    timeline = Timeline(
        CAPRecruiterStandardConsent(),
        InfoPage("Welcome to the experiment!", time_estimate=5),
        Module(
            "introduction",
            PageMaker(
                lambda: InfoPage(
                    f"The current time is {datetime.now().strftime('%H:%M:%S')}."
                ),
                time_estimate=5,
            ),
            ModularPage(
                "message",
                "Write me a message!",
                control=TextControl(one_line=False),
                time_estimate=5,
                save_answer=True,
            ),
            PageMaker(
                lambda participant: InfoPage(
                    f"Your message: {participant.deliberately_cause_an_error}"
                ),
                time_estimate=5,
            ),
        ),
        SuccessfulEndPage(),
    )
