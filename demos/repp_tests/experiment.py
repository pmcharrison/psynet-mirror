# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################
import psynet.experiment

from psynet.timeline import Timeline,PreDeployRoutine
from psynet.media import prepare_s3_bucket_for_presigned_urls


from psynet.prescreen import REPPVolumeCalibrationMusic, REPPVolumeCalibrationMarkers, REPPTappingCalibration, REPPMarkersCheck
from psynet.page import SuccessfulEndPage, InfoPage

##########################################################################################
#### Experiment
##########################################################################################

class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {"bucket_name": "markers-check-recordings", "public_read": True, "create_new_bucket": True} # s3 bucket to store markers check recordings
        ),
        REPPVolumeCalibrationMarkers(), # Volume calibration test for metronome: adjust right volume to be used with REPP when working with metronome stimuli
    	REPPVolumeCalibrationMusic(), # Volume calibration test for music: adjust right volume to be used with REPP when working with music sitmuli
    	REPPTappingCalibration(), # Calibration test 2: adjust tapping volume to be used with REPP
    	REPPMarkersCheck(),
        InfoPage("You passed the recording test! Congratulations.", time_estimate=3),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
