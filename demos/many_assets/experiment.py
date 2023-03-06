# pylint: disable=unused-import,abstract-method,unused-argument

# The purpose of this experiment is to test whether PsyNet can handle many External Assets in the same
# experiment without taking unnecessarily long to deploy.

import psynet.experiment
from psynet.asset import ExternalAsset
from psynet.consent import MainConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Module, Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Test many external assets"

    variables = {
        "show_abort_button": True,
    }

    timeline = Timeline(
        MainConsent(),
        Module(
            "asset_test",
            InfoPage("Welcome to the experiment!", time_estimate=5),
            assets={
                f"asset_{i}": ExternalAsset(url=f"https://google.com/images/asset_{i}")
                for i in range(1000)
            },
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
