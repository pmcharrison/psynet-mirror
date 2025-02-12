import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage, VolumeCalibration
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Volume calibration"

    timeline = Timeline(
        NoConsent(),
        VolumeCalibration(),
        SuccessfulEndPage(),
    )
