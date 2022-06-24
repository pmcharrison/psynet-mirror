import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import CodeBlock, InfoPage, PageMaker, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        InfoPage(
            "This demo illustrates page pickling.",
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.var.set(
                "page", InfoPage("This page was pickled in the database.")
            )
        ),
        PageMaker(lambda participant: participant.var.page, time_estimate=5),
        SuccessfulEndPage(),
    )
