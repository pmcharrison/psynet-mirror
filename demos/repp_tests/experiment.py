# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    FreeTappingRecordTest,
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMarkers,
    REPPVolumeCalibrationMusic,
)
from psynet.timeline import PreDeployRoutine, Timeline

# TODO - this needs updating


# Experiment
class Exp(psynet.experiment.Experiment):
    label = "REPP tests demo"

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
        # volume calibration tests
        REPPVolumeCalibrationMarkers(),  # Use this for SMS experiemnts with markers
        REPPVolumeCalibrationMusic(),  # Use this for expeeriments using music
        # tappingn instructions and calibration
        REPPTappingCalibration(),
        # recording tests
        FreeTappingRecordTest(),  # Use this for unconstrained tapping experiment (without markers).
        InfoPage(
            "You passed the tapping recording test! Congratulations.", time_estimate=3
        ),
        REPPMarkersTest(),  # Use this for SMS tapping experiments (with markers).
        InfoPage("You passed the recording test! Congratulations.", time_estimate=3),
        SuccessfulEndPage(),
    )
