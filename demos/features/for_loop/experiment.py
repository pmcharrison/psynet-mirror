import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Timeline, for_loop
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "For loop demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        for_loop(
            label="Looping over letters A-C",
            iterate_over=lambda: ["A", "B", "C"],
            logic=lambda letter: for_loop(
                label="Looping over numbers 1-3",
                iterate_over=lambda: [1, 2, 3],
                logic=lambda number: InfoPage(f"{letter}{number}"),
                time_estimate_per_iteration=5,
            ),
            time_estimate_per_iteration=15,
        ),
        for_loop(
            label="Looping over letters D-F",
            iterate_over=lambda: ["D", "E", "F"],
            logic=lambda letter: InfoPage(f"{letter}"),
            time_estimate_per_iteration=5,
        ),
    )

    def test_run_bot(self, bot):
        expected = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D", "E", "F"]
        for exp in expected:
            assert bot.get_current_page().prompt == exp
            bot.take_page()
        bot.run_to_completion()
