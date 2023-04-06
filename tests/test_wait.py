import logging

import pytest

from psynet.bot import Bot
from psynet.pytest_psynet import bot_class, path_to_demo

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize("experiment_directory", [path_to_demo("wait")], indirect=True)
class TestExp:
    def test_exp(self, launched_experiment):
        bot = Bot()

        bot.take_experiment()

        assert (bot.var.end_time - bot.var.start_time).total_seconds() > 3
