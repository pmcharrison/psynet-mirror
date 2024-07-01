import pytest

from psynet.bot import Bot
from psynet.pytest_psynet import path_to_demo_feature


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_feature("wait")], indirect=True
)
class TestExp:
    def test_exp(self, launched_experiment):
        bot = Bot()

        bot.take_experiment()

        assert (bot.var.end_time - bot.var.start_time).total_seconds() > 3
