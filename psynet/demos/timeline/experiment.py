import psynet.experiment
from psynet.timeline import (
    Timeline,
    PageMaker,
    CodeBlock,
    while_loop,
    conditional,
    switch,
    Module
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    NAFCPage,
    TextInputPage,
)

from psynet.utils import get_logger
logger = get_logger()

from datetime import datetime

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        InfoPage(
            "Welcome to the experiment!",
            time_estimate=5
        ),
        Module(
            "introduction",
            PageMaker(
                lambda experiment, participant:
                    InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
                time_estimate=5
            ),
            TextInputPage(
                "message",
                "Write me a message!",
                time_estimate=5,
                one_line=False
            ),
            PageMaker(
                lambda participant: InfoPage(f"Your message: {participant.answer}"),
                time_estimate=5
            )
        ),
        Module(
            "chocolate",
            NAFCPage(
                label="chocolate",
                prompt="Do you like chocolate?",
                choices=["Yes", "No"],
                time_estimate=3,
                arrange_vertically=True
            ),
            conditional(
                "like_chocolate",
                lambda experiment, participant: participant.answer == "Yes",
                InfoPage(
                    "It's nice to hear that you like chocolate!",
                    time_estimate=5
                ),
                InfoPage(
                    "I'm sorry to hear that you don't like chocolate...",
                    time_estimate=3
                ),
                fix_time_credit=False
            )
        ),
        CodeBlock(lambda experiment, participant: participant.set_answer("Yes")),
        while_loop(
            "example_loop",
            lambda experiment, participant: participant.answer == "Yes",
            Module(
                "loop",
                NAFCPage(
                    label="loop_nafc",
                    prompt="Would you like to stay in this loop?",
                    choices=["Yes", "No"],
                    time_estimate=3
                ),
            ),
            expected_repetitions=3,
            fix_time_credit=True
        ),
        Module(
            "colour",
            NAFCPage(
                label="test_nafc",
                prompt="What's your favourite colour?",
                choices=["Red", "Green", "Blue"],
                time_estimate=5
            ),
            CodeBlock(
                lambda experiment, participant:
                participant.var.new("favourite_colour", participant.answer)
            ),
            switch(
                "colour",
                lambda experiment, participant: participant.answer,
                branches = {
                    "Red": InfoPage("Red is a nice colour, wait 1s.", time_estimate=1),
                    "Green": InfoPage("Green is quite a nice colour, wait 2s.", time_estimate=2),
                    "Blue": InfoPage("Blue is an unpleasant colour, wait 3s.", time_estimate=3)
                },
                fix_time_credit=False
            )
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
