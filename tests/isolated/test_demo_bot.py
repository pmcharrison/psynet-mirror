import logging

import pytest

from psynet.bot import Bot
from psynet.pytest_psynet import bot_class, path_to_demo

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize("experiment_directory", [path_to_demo("bot")], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_exp(self):
        bots = [Bot() for _ in range(2)]

        for bot in bots:
            bot.take_experiment()

        assert bots[0].id == 1
        assert bots[1].id == 2

        assert not bots[0].failed
        assert bots[1].failed

        bot_1_answers = [r.answer for r in bots[0].all_responses]

        assert bot_1_answers[0] == "Fixed response"
        assert bot_1_answers[1].startswith("Stochastic response")
        assert (
            bot_1_answers[2] == "This response came from the CustomTextControl method."
        )
