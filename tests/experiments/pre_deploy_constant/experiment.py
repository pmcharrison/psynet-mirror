import os

import psynet.experiment
from psynet.bot import Bot
from psynet.experiment import pre_deploy_constant
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, Timeline

local_machine_cwd = pre_deploy_constant("local_machine_cwd", lambda: os.getcwd())
data_files = pre_deploy_constant("data_files", lambda: os.listdir("data"))


class Exp(psynet.experiment.Experiment):
    label = "Pre-deploy constant"

    timeline = Timeline(
        InfoPage(
            """
            We need at least one page at the start of the timeline, otherwise the code blocks will be evaluated immediately
            on initialization of the testing script, and this will result in the code being run in the test directory
            rather than the deployment directory.
            """,
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.var.set(
                "local_machine_cwd", local_machine_cwd
            )
        ),
        CodeBlock(lambda participant: participant.var.set("runtime_cwd", os.getcwd())),
        CodeBlock(lambda participant: participant.var.set("data_files", data_files)),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert bot.var.get("local_machine_cwd") != bot.var.get("runtime_cwd")
        assert "file1" in bot.var.get("data_files")
        assert "file2" in bot.var.get("data_files")
