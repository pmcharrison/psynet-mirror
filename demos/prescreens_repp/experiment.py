# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
from statistics import mean
import random
import re
from typing import Union, List
import time
from dallinger import db

import psynet.experiment

from psynet.timeline import get_template, join
from psynet.field import claim_field
from psynet.participant import Participant, get_participant
from psynet.timeline import Timeline,PreDeployRoutine
from psynet.media import make_bucket_public, download_from_s3, prepare_s3_bucket_for_presigned_urls


from psynet.prescreen import REPPVolumeCalibration, REPPTappingCalibration, REPPMarkersCheck
from psynet.page import SuccessfulEndPage, InfoPage, DebugResponsePage, VolumeCalibration

# for REPP to work in MarkersCheck
import tapping_extract as tapping
from scipy.io import wavfile
from scipy.io.wavfile import write
from math import nan
import numpy as np

##########################################################################################
#### Experiment
##########################################################################################

#languages avaialble in LanguageVocabularyTest: English_US, German, Hindi, Portuguese_BR, Spanish_SP

class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {"bucket_name": "markers-check-recordings", "public_read": True, "create_new_bucket": True} # s3 bucket to store markers check reocrings
        ),
    	REPPVolumeCalibration(), # Calibration test 1: adjust right volume to be used with REPP
    	REPPTappingCalibration(), # Calibration test 2: adjust tapping volume to be used with REPP
    	REPPMarkersCheck(),
        InfoPage("You passed the recording test! Congratulations.", time_estimate=3),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
