import pytest
from click import Context

from psynet.pytest_psynet import bot_class, path_to_demo_experiment

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_demo_experiment("rock_paper_scissors")],
    indirect=True,
)
class TestExp(object):
    def test(self, in_experiment_directory):
        from psynet.command_line import test__local

        ctx = Context(test__local)
        ctx.invoke(test__local, parallel=True, n_bots=10)
