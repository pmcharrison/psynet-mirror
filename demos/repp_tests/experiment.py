# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.asset import DebugStorage, S3Storage  # noqa
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    FreeTappingRecordTest,
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMarkers,
    REPPVolumeCalibrationMusic,
)
from psynet.timeline import Timeline


# Experiment
class Exp(psynet.experiment.Experiment):
    label = "REPP tests demo"

    # asset_storage = S3Storage("psynet-demos", "repp-tests")
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        # Volume calibration tests
        REPPVolumeCalibrationMarkers(),  # Use this for SMS experiemnts with markers
        REPPVolumeCalibrationMusic(),  # Use this for experiments using music
        REPPTappingCalibration(),  # Tapping instructions and calibration
        # Recording tests
        FreeTappingRecordTest(),  # Use this for unconstrained tapping experiment (without markers).
        InfoPage(
            "You passed the tapping recording test! Congratulations.", time_estimate=3
        ),
        REPPMarkersTest(),  # Use this for SMS tapping experiments (with markers).
        InfoPage("You passed the recording test! Congratulations.", time_estimate=3),
        SuccessfulEndPage(),
    )
