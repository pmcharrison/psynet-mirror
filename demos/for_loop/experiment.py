import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline, for_loop
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "For loop demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        for_loop(
            "Looping over letters A-C",
            lambda: ["A", "B", "C"],
            lambda letter: for_loop(
                "Looping over numbers 1-3",
                [1, 2, 3],
                lambda number: InfoPage(f"{letter}{number}"),
                time_estimate_per_iteration=5,
            ),
            time_estimate_per_iteration=15,
        ),
        for_loop(
            "Looping over letters D-F",
            ["D", "E", "F"],
            lambda letter: InfoPage(f"{letter}"),
            time_estimate_per_iteration=5,
        ),
        SuccessfulEndPage(),
    )

    def test_run_bot(self, bot):
        expected = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D", "E", "F"]
        for exp in expected:
            assert bot.get_current_page().prompt == exp
            bot.take_page()
        bot.run_to_completion()
