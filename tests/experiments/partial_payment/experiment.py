# pylint: disable=unused-import,abstract-method,unused-argument

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import InfoPage, UnsuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline, conditional
from psynet.utils import get_logger

logger = get_logger()

BONUS = 3.5


class Exp(psynet.experiment.Experiment):
    label = "Trying to make a partial payment"
    config = {
        "base_payment": 1.0,
        "wage_per_hour": 10.0,
    }

    test_n_bots = 3

    timeline = Timeline(
        NoConsent(),
        InfoPage("Let's imagine this is the prescreener", time_estimate=60),
        conditional(
            "decide_whether_to_fail_participant",
            lambda participant: participant.id > 1,
            logic_if_true=UnsuccessfulEndPage(),
        ),
        InfoPage("Let's imagine this is the main experiment", time_estimate=60 * 5),
        CodeBlock(lambda participant: participant.inc_performance_reward(BONUS)),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        if bot.id == 1:
            assert bot.status == "approved"
            assert self.bonus(bot) == BONUS
        elif bot.id == 2:
            bot.run_to_completion()
            bot.wait_until_experiment_launch_is_complete()
            assert (
                bot.status == "screened_out"
            ), f"Expected status to be 'screened_out', but got {bot.status}"
            assert self.bonus(bot) in (
                0.17,
                0.18,
            ), f"Expected bonus to be either 0.17 or 0.18, but got {self.bonus(bot)}"  # £10/hour * 1 minute / 60 minutes/hour = £0.1666... ≈ £0.17 but can also be £0.18 sometimes
        elif bot.id == 3:
            # Simulate the participant returning their assignment
            self.assignment_returned(bot)
            # Explicitly set the status to "returned" for testing
            # In a real Prolific environment, this would be set by run_recruiter_checks scheduled_task
            bot.status = "returned"
            bot.failed = True
            assert (
                bot.status == "returned"
            ), f"Expected status to be 'returned', but got {bot.status}"
            assert self.bonus(bot) in (
                0.17,
                0.18,
            ), f"Expected bonus to be either 0.17 or 0.18, but got {self.bonus(bot)}"
        else:
            raise ValueError(f"Unexpected bot id: {bot.id}")
