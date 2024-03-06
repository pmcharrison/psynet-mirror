import psynet.experiment
from psynet.asset import LocalStorage
from psynet.consent import NoConsent
from psynet.page import PageMaker, SuccessfulEndPage, VolumeCalibration
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Volume calibration"
    asset_storage = LocalStorage()

    timeline = Timeline(
        NoConsent(),
        PageMaker(
            # We put this inside a page maker to confirm that it is indeed possible
            # to declare assets within a page maker.
            lambda: VolumeCalibration(),
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )
