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
        "base_payment": 10 * 6 / 60,  # £10/hour * 6 minutes / 60 minutes/hour
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
            print(bot.id)
            print(bot.status)
            print(bot.bonus)
            assert bot.status == "approved"
            assert bot.performance_reward == BONUS  # Why is bonus not set?
        elif bot.id == 2:
            print(bot.id)
            print(bot.status)
            print(bot.bonus)
            # assert bot.status == "screened_out"
            # assert bot.bonus == 1 * 6 / 60  # £10/hour * 1 minute / 60 minutes/hour
        elif bot.id == 3:
            print(bot.id)
            print(bot.status)
            print(bot.bonus)
            # assert bot.status == "returned"
            # assert bot.bonus == 1 * 6 / 60  # £10/hour * 1 minute / 60 minutes/hour
        else:
            raise ValueError(f"Unexpected bot id: {bot.id}")
