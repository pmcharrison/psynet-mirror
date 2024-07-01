# pylint: disable=unused-import,abstract-method,unused-argument

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import MainConsent
from psynet.page import InfoPage, SuccessfulEndPage, UnsuccessfulEndPage
from psynet.timeline import CodeBlock, ParticipantFailRoutine, Timeline, switch
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Failing a participant"

    test_n_bots = 3

    timeline = Timeline(
        MainConsent(),
        CodeBlock(
            lambda participant: participant.var.set("fail_routine_executed", False)
        ),
        switch(
            "switch",
            lambda participant: participant.id,
            {
                1: InfoPage("Nothing to see here...", time_estimate=5),
                2: UnsuccessfulEndPage(),
                3: CodeBlock(lambda participant: participant.fail("CodeBlock")),
            },
        ),
        ParticipantFailRoutine(
            "var",
            lambda participant: participant.var.set("fail_routine_executed", True),
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        if bot.id == 1:
            assert not bot.failed
            assert not bot.var.fail_routine_executed
        else:
            assert bot.failed
            assert bot.var.fail_routine_executed

            if bot.id == 2:
                assert bot.failed_reason == "UnsuccessfulEndPage"

            elif bot.id == 3:
                assert bot.failed_reason == "CodeBlock"

            else:
                raise ValueError(f"Unexpected bot id: {bot.id}")
