import pytest
from dallinger import db

from psynet.bot import Bot, BotDriver
from psynet.error import ErrorRecord
from psynet.experiment import Experiment
from psynet.process import WorkerAsyncProcess
from psynet.pytest_psynet import path_to_demo_experiment
from psynet.utils import wait_until


def run_bot():
    bot = BotDriver()
    bot.take_experiment(time_factor=0.9)


def run_bot_group(experiment: Experiment):
    for _ in range(3):
        WorkerAsyncProcess(function=experiment.run_bot)
        db.session.commit()

    wait_until(
        lambda: count_working_bots() == 3 or count_errors() > 0,
        max_wait=5,
        poll_interval=0.25,
    )
    assert count_errors() == 0

    wait_until(
        lambda: count_working_bots() == 0 or count_errors() > 0,
        max_wait=30,
        poll_interval=1.0,
    )
    assert count_errors() == 0

    for bot in Bot.query.all():
        assert not bot.failed


def count_working_bots():
    return Bot.query.filter_by(status="working").count()


def count_errors():
    return ErrorRecord.query.count()


@pytest.mark.usefixtures("launched_experiment")
@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_demo_experiment("gibbs_within_sync")],
    indirect=True,
)
def test_run_bots(launched_experiment):
    if hasattr(launched_experiment, "bot_launcher"):
        raise RuntimeError(
            "The bot_launcher method should be commented out for running tests."
        )

    run_bot_group(launched_experiment)
    assert ErrorRecord.query.count() == 0
    run_bot_group(launched_experiment)
    assert ErrorRecord.query.count() == 0


# TODO: introduce a test with random failures?
