from datetime import datetime
from typing import List

import numpy
import requests
from dallinger.experiment import experiment_route
from dominate import tags

import psynet.experiment
from psynet.bot import Bot
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
from psynet.recruiters import DevLucidRecruiter, MTurkRecruiter, ProlificRecruiter
from psynet.timeline import (
    CodeBlock,
    Module,
    PageMaker,
    Timeline,
    conditional,
    switch,
    while_loop,
)


class Exp(psynet.experiment.Experiment):
    label = "Timeline demo"
    initial_recruitment_size = 1

    variables = {
        "new_variable": "some-value",
    }

    config = {
        "lucid_api_key": "secret",
        "lucid_sha1_hashing_key": "secret",
        "lucid_recruitment_config": "file:./lucid_recruitment_config.json",
        "min_accumulated_reward_for_abort": 0.15,
        "show_abort_button": True,
        "show_reward": False,
    }

    @experiment_route("/custom_route", methods=["POST", "GET"])
    @classmethod
    def custom_route(cls):
        return f"A custom route for {cls.__name__}."

    timeline = Timeline(
        MainConsent(),
        InfoPage(
            tags.div(
                tags.h2("Welcome"),
                tags.p("Welcome to the experiment!"),
            ),
            time_estimate=5,
        ),
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
                tags.p(
                    "Write me a ",
                    tags.span("message", style="color: red"),
                    "!",
                ),
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
                InfoPage("It's nice to hear that you like chocolate!", time_estimate=6),
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
                        "shape",
                        Prompt(f"Participant {participant.id}, choose a shape:"),
                        control=PushButtonControl(
                            ["Square", "Circle"], arrange_vertically=False
                        ),
                        time_estimate=5,
                    ),
                    ModularPage(
                        "chord",
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
                        "If accumulate_answers is True, then the answers are stored in a dictionary, in this case: "
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

    def with_recruiter(self, nickname):
        # We use this for patching the recruiter while testing the recruiter UI
        if self.var.has("with_recruiter"):
            patched_recruiter = self.var.with_recruiter
            if nickname == "mturk":
                self.recruiter = MTurkRecruiter(skip_config_validation=True)
            elif nickname == "prolific":
                self.recruiter = ProlificRecruiter()
            elif nickname == "lucid":
                self.recruiter = DevLucidRecruiter()
            return nickname == patched_recruiter
        return super().with_recruiter(nickname)

    def take_page_and_make_request(self, bot):
        bot.take_page(bot.get_current_page(), response={"main_consent": False})
        return requests.get(f"http://localhost:5000/timeline?unique_id={bot.unique_id}")

    test_n_bots = 4

    def run_bot(self, bot):
        # Hotair
        if bot.id == 1:
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." in str(req.content)
            assert "End of experiment." in str(req.content)
            assert 'Please click "Finish" to complete the experiment.' in str(
                req.content
            )
            bot.run_to_completion()

        # Lucid
        if bot.id == 2:
            self.var.with_recruiter = "lucid"
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." not in str(req.content)
            assert "End of experiment." not in str(req.content)
            bot.run_to_completion()

        # MTurk
        if bot.id == 3:
            self.var.with_recruiter = "mturk"
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." in str(req.content)
            assert "End of experiment." in str(req.content)
            assert 'Please click "Finish" to complete the HIT.' in str(req.content)
            bot.run_to_completion()

        # Prolific
        if bot.id == 4:
            self.var.with_recruiter = "prolific"
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." in str(req.content)
            assert "End of experiment." in str(req.content)
            assert 'Please click "Finish" to complete the study.' in str(req.content)
            bot.run_to_completion()

    def test_check_bots(self, bots: List[Bot]):
        super().test_check_bots(bots, failed=True)
