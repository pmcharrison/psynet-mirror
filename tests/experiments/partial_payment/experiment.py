"""
This experiment tests different routes of participant payment in PsyNet, specifically focusing on:
1. Full payment with bonus (approved participants)
2. Partial payment for screened-out participants
3. Partial payment for returned assignments

Payment Routes:
---------------
1. Approved Participants (ID=1):
   - Base payment: £1.00
   - Bonus: £3.50
   - Total: £4.50
   - Route: Completes full experiment

2. Screened-out Participants (ID=2):
   - Partial payment: ~£0.17-0.18 (based on time spent)
   - No bonus
   - Route: Fails at prescreener stage

3. Returned Assignment (ID=3):
   - Partial payment: ~£0.17-0.18 (based on time spent)
   - No bonus
   - Route: Assignment is returned after completion

The experiment uses participant.var to track the route taken through the timeline,
which is then verified in the test_check_bot method.
"""

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
        # "base_payment": 1.0, # Uncomment this and comment base_payment in the config.py file when deploying
        "wage_per_hour": 10.0,
        "prolific_workspace": "test_workspace",
        "prolific_project": "test_project",
        "prolific_enable_screen_out": True,
    }

    test_n_bots = 3

    timeline = Timeline(
        NoConsent(),
        InfoPage("Let's imagine this is the prescreener", time_estimate=60),
        CodeBlock(
            lambda participant: participant.var.set("route", "prescreener_completed")
        ),
        conditional(
            "decide_whether_to_fail_participant",
            lambda participant: participant.id == 2,
            logic_if_true=[
                CodeBlock(
                    lambda participant: participant.var.set("route", "screened_out")
                ),
                UnsuccessfulEndPage(),
            ],
        ),
        conditional(
            "decide_whether_to_fail_participant",
            lambda participant: participant.id == 3,
            logic_if_true=[
                CodeBlock(
                    lambda participant: participant.var.set(
                        "route", "returned_and_screened_out"
                    )
                ),
                UnsuccessfulEndPage(),
            ],
        ),
        InfoPage("Let's imagine this is the main experiment", time_estimate=60 * 5),
        CodeBlock(
            lambda participant: participant.var.set(
                "route", "main_experiment_completed"
            )
        ),
        CodeBlock(lambda participant: participant.inc_performance_reward(BONUS)),
        CodeBlock(lambda participant: participant.var.set("route", "bonus_awarded")),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        route = bot.var.get("route")

        if bot.id == 1:
            assert (
                route == "bonus_awarded"
            ), f"Expected route 'bonus_awarded', got '{route}'"
            assert (
                bot.status == "approved"
            ), f"Expected status for bot ID {bot.id} to be 'approved', but got '{bot.status}'"
            # Ensure the status is committed and refresh the bot object to get the latest status
            from psynet.experiment import db

            db.session.commit()
            db.session.refresh(bot)

            assert self.base_payment == 1.0

            assert (
                self.bonus(bot) == BONUS
            ), f"Expected bonus for bot ID {bot.id} to be 3.5, but got {self.bonus(bot)} (status: {bot.status}, time_reward: {bot.time_reward}, performance_reward: {bot.performance_reward}, bot.bonus: {bot.bonus})"
        elif bot.id == 2:
            assert (
                route == "screened_out"
            ), f"Expected route 'screened_out', got '{route}'"
            assert (
                bot.status == "screened_out"
            ), f"Expected status for bot ID {bot.id} to be 'screened_out', but got '{bot.status}'"
            assert self.bonus(bot) in (
                0.17,
                0.18,
            ), f"Expected bonus for bot ID {bot.id} to be either 0.17 or 0.18, but got {self.bonus(bot)}"
        elif bot.id == 3:
            assert (
                route == "returned_and_screened_out"
            ), f"Expected route 'returned_and_screened_out', got '{route}'"
            # Simulate the participant returning their assignment
            self.assignment_returned(bot)
            # Explicitly set the status to "returned" for testing
            # In a real Prolific environment, this would be set by run_recruiter_checks scheduled_task
            bot.status = "returned"
            bot.failed = True
            assert (
                bot.status == "returned"
            ), f"Expected status for bot ID {bot.id} to be 'returned', but got '{bot.status}'"
            assert self.bonus(bot) in (
                0.17,
                0.18,
            ), f"Expected bonus for bot ID {bot.id} to be either 0.17 or 0.18, but got {self.bonus(bot)}"
        else:
            raise ValueError(f"Unexpected bot id: {bot.id}")
