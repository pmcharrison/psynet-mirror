import psynet.experiment
from psynet.consent import MainConsent
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, Timeline


class Exp(psynet.experiment.Experiment):
    label = "Log dump error test"

    timeline = Timeline(
        MainConsent(),
        InfoPage("Starting log dump error test", time_estimate=1),
        CodeBlock(
            lambda participant: participant.var.set(
                "broken", undefined_var  # noqa: F821
            )
        ),
        InfoPage("This page should never be reached", time_estimate=1),
    )
