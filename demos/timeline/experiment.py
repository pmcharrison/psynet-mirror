from datetime import datetime

import numpy
from dallinger.experiment import experiment_route

import psynet.experiment
from psynet.consent import MainConsent
from psynet.modular_page import (
    ModularPage,
    NumberControl,
    Prompt,
    PushButtonControl,
    TextControl,
    TimedPushButtonControl,
)
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import (
    CodeBlock,
    Module,
    PageMaker,
    Timeline,
    conditional,
    switch,
    while_loop,
)
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

    variables = {
        "show_abort_button": True,
        "min_accumulated_bonus_for_abort": 0.15,
        "wage_per_hour": 12.0,
        "new_variable": "some-value",
        # "show_footer": False,  # uncomment to disable the footer (bonus + help button)
        # "show_progress_bar": False,  # uncomment to disable the progress bar
    }

    @experiment_route("/custom_route", methods=["POST", "GET"])
    @classmethod
    def custom_route(cls):
        return f"A custom route for {cls.__name__}."

    timeline = Timeline(
        MainConsent(),
        InfoPage("Welcome to the experiment!", time_estimate=5),
        Module(
            "introduction",
            # You can set arbitrary variables with the participant object
            # inside code blocks. Here we set a variable called 'numpy_test',
            # and the value is an object from the numpy package (numpy.nan).
            CodeBlock(lambda participant: participant.var.set("numpy_test", numpy.nan)),
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
                lambda participant: InfoPage(f"Your message: {participant.answer}"),
                time_estimate=5,
            ),
        ),
        Module(
            "weight",
            ModularPage(
                "weight",
                Prompt("What is your weight in kg?"),
                NumberControl(),
                time_estimate=5,
                save_answer="weight",
            ),
            PageMaker(
                lambda participant: InfoPage(
                    f"Your weight is {participant.var.weight} kg."
                ),
                time_estimate=5,
            ),
        ),
        ModularPage(
            "timed_push_button",
            Prompt(
                """
                This is a TimedPushButtonControl. You can press the buttons 'A', 'B', 'C'
                in any order, as many times as you like, and the timings will be logged.
                Press 'Next' when you're ready to continue.
                """
            ),
            TimedPushButtonControl(choices=["A", "B", "C"], arrange_vertically=False),
            time_estimate=5,
        ),
        Module(
            "chocolate",
            ModularPage(
                "chocolate",
                Prompt("Do you like chocolate?"),
                control=PushButtonControl(["Yes", "No"]),
                time_estimate=3,
            ),
            conditional(
                "like_chocolate",
                lambda participant: participant.answer == "Yes",
                InfoPage("It's nice to hear that you like chocolate!", time_estimate=5),
                InfoPage(
                    "I'm sorry to hear that you don't like chocolate...",
                    time_estimate=3,
                ),
                fix_time_credit=False,
            ),
        ),
        CodeBlock(lambda participant: participant.set_answer("Yes")),
        while_loop(
            "example_loop",
            lambda participant: participant.answer == "Yes",
            Module(
                "loop",
                ModularPage(
                    "loop_nafc",
                    Prompt("Would you like to stay in this loop?"),
                    control=PushButtonControl(["Yes", "No"], arrange_vertically=False),
                    time_estimate=3,
                ),
            ),
            expected_repetitions=3,
            fix_time_credit=True,
        ),
        Module(
            "PageMaker with multiple pages",
            InfoPage(
                """
                It is possible to generate multiple pages from the same
                PageMaker, as in the following example:
                """,
                time_estimate=5,
            ),
            PageMaker(
                lambda participant: [
                    ModularPage(
                        "mp1",
                        Prompt(f"Participant {participant.id}, choose a shape:"),
                        control=PushButtonControl(
                            ["Square", "Circle"], arrange_vertically=False
                        ),
                        time_estimate=5,
                    ),
                    ModularPage(
                        "mp2",
                        Prompt(f"Participant {participant.id}, choose a chord:"),
                        control=PushButtonControl(
                            ["Major", "Minor"], arrange_vertically=False
                        ),
                        time_estimate=5,
                    ),
                ],
                time_estimate=10,
                accumulate_answers=True,
            ),
            PageMaker(
                lambda participant: InfoPage(
                    (
                        "If accumulate_answers is True, then the answers are stored in a list, in this case: "
                        + f"{participant.answer}."
                    ),
                    time_estimate=5,
                ),
                time_estimate=5,
            ),
        ),
        Module(
            "color",
            ModularPage(
                "test_nafc",
                Prompt("What's your favourite color?"),
                control=PushButtonControl(
                    ["Red", "Green", "Blue"], arrange_vertically=False
                ),
                time_estimate=5,
            ),
            CodeBlock(
                lambda participant: participant.var.new(
                    "favourite_color", participant.answer
                )
            ),
            switch(
                "color",
                lambda participant: participant.answer,
                branches={
                    "Red": InfoPage("Red is a nice color, wait 1s.", time_estimate=1),
                    "Green": InfoPage(
                        "Green is quite a nice color, wait 2s.", time_estimate=2
                    ),
                    "Blue": InfoPage(
                        "Blue is an unpleasant color, wait 3s.", time_estimate=3
                    ),
                },
                fix_time_credit=False,
            ),
        ),
        SuccessfulEndPage(),
    )
