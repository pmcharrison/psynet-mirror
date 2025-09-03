import os

import psynet.experiment
from psynet.bot import Bot
from psynet.experiment import pre_deploy_constant
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, PageMaker, Timeline

# PsyNet does not include the 'data' directory in the deployment package,
# so we need to create a pre-deploy constant for lists of data files.
data_files = pre_deploy_constant("data_files", lambda: sorted(os.listdir("data")))
local_machine_cwd = pre_deploy_constant("local_machine_cwd", lambda: os.getcwd())


class Exp(psynet.experiment.Experiment):
    label = "Pre-deploy constant"

    timeline = Timeline(
        PageMaker(
            lambda: InfoPage(
                f"""
Pre-deploy constants are used to store values that can only be computed on the local machine,
not on the deployed machine. For example, the 'data' directory is only available on the local machine,
so we need to use a pre-deploy constant to store the list of files in the 'data' directory.
In this case, `data_files` has taken the following value: `{data_files}`.
"""
            ),
            time_estimate=10,
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
