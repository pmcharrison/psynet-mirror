import psynet.experiment
from psynet.bot import Bot
from psynet.page import wait_while
from psynet.timeline import CodeBlock, Timeline
from psynet.utils import code_block_process_finished, get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Demo demonstrating asynchronous CodeBlock execution"
    initial_recruitment_size = 1

    def set_participant_var(participant):
        participant.var.set("test_async", "SUCCESS")

    timeline = Timeline(
        CodeBlock(
            set_participant_var,
            is_async=True,
        ),
        wait_while(
            condition=lambda participant: not code_block_process_finished(participant),
            expected_wait=3,
            check_interval=0.5,
        ),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert bot.var.test_async == "SUCCESS"
