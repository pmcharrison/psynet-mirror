# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMarkers,
    REPPVolumeCalibrationMusic,
)
from psynet.timeline import PreDeployRoutine, Timeline


# Experiment
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {
                "bucket_name": "markers-check-recordings",
                "public_read": True,
                "create_new_bucket": True,
            },  # s3 bucket to store markers check recordings
        ),
        REPPVolumeCalibrationMarkers(),  # Volume calibration test for markers
        REPPVolumeCalibrationMusic(),  # Volume calibration test for music
        REPPTappingCalibration(),  # Calibration test 2: adjust tapping volume to be used with REPP
        REPPMarkersTest(),
        InfoPage("You passed the recording test! Congratulations.", time_estimate=3),
        SuccessfulEndPage(),
    )
