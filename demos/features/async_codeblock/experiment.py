import psynet.experiment
from psynet.bot import Bot
from psynet.page import wait_while
from psynet.timeline import CodeBlock, Timeline
from psynet.utils import code_block_process_finished, get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Demo demonstrating asynchronous CodeBlock execution"
    initial_recruitment_size = 1

    def set_participant_var1(participant):
        participant.var.set("async1", "ASYNC 1")

    def set_participant_var2(participant):
        participant.var.set("async2", "ASYNC 2")

    timeline = Timeline(
        CodeBlock(
            set_participant_var1,
            async_=True,
            label="async1",
        ),
        CodeBlock(
            set_participant_var2,
            async_=True,
            label="async2",
        ),
        wait_while(
            condition=lambda participant: not code_block_process_finished(
                participant, "async1"
            ),
            expected_wait=3,
            check_interval=0.5,
        ),
        wait_while(
            condition=lambda participant: not code_block_process_finished(
                participant, "async2"
            ),
            expected_wait=3,
            check_interval=0.5,
        ),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert bot.var.async1 == "ASYNC 1"
        assert bot.var.async2 == "ASYNC 2"
