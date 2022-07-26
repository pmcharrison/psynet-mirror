import logging

import pytest

from psynet.bot import Bot
from psynet.test import bot_class

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_wait")
class TestExp:
    def test_exp(self, active_config, debug_experiment):
        bot = Bot()

        bot.take_experiment()

        assert (bot.var.end_time - bot.var.start_time).total_seconds() > 3
