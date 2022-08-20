import logging

import pytest

from psynet.bot import Bot
from psynet.test import bot_class

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize("experiment_directory", ["../demos/bot"], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_exp(self, active_config):
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
