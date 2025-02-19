import psynet.experiment
from psynet.bot import Bot
from psynet.page import wait_while
from psynet.timeline import CodeBlock, Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Demo demonstrating an asynchronous CodeBlock"
    initial_recruitment_size = 1

    def set_async_flag(participant):
        participant.var.set("test_async", "SUCCESS")

    def check_async_flag(participant):
        return participant.var.get("test_async", None) != "SUCCESS"

    # TODO raise if a lambda function was supplied
    timeline = Timeline(
        CodeBlock(
            set_async_flag,
            is_async=True,
        ),
        wait_while(
            check_async_flag,
            expected_wait=3,
            check_interval=0.5,
        ),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert bot.var.test_async == "SUCCESS"
