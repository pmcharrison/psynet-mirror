# pylint: disable=unused-import,abstract-method,unused-argument

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import MainConsent
from psynet.page import SuccessfulEndPage, UnsuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline, switch
from psynet.utils import get_logger

logger = get_logger()

assert False, "Check that the CI is running this test"


class Exp(psynet.experiment.Experiment):
    label = "Failing a participant"

    test_n_bots = 2

    timeline = Timeline(
        MainConsent(),
        switch(
            "switch",
            lambda participant: participant.id % 2,
            {
                0: UnsuccessfulEndPage(),
                1: CodeBlock(lambda participant: participant.fail("CodeBlock")),
            },
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert bot.failed

        if bot.id % 2 == 0:
            assert bot.failed_reason == "UnsuccessfulEndPage"
        else:
            assert bot.failed_reason == "CodeBlock"
