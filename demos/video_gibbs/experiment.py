# pylint: disable=unused-import,abstract-method,unused-argument,no-member

# Note: ffmpeg must be installed

##########################################################################################
# Imports
##########################################################################################

from flask import Markup

import psynet.experiment
import psynet.media
from psynet.consent import CAPRecruiterAudiovisualConsent, CAPRecruiterStandardConsent
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.media_gibbs import (
    VideoGibbsNetwork,
    VideoGibbsNode,
    VideoGibbsSource,
    VideoGibbsTrial,
    VideoGibbsTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()

# Custom parameters, change these as you like!
TARGETS = ["positive", "energetic"]
DURATION_RANGE = [0.1, 1.5]
RGB_RANGE = [0, 255]
VECTOR_RANGES = [
    RGB_RANGE,
    RGB_RANGE,
    RGB_RANGE,
    RGB_RANGE,
    RGB_RANGE,
    RGB_RANGE,
    DURATION_RANGE,
    DURATION_RANGE,
]
DIMENSIONS = len(VECTOR_RANGES)
GRANULARITY = 25  # 25 different slider positions
SNAP_SLIDER = True
AUTOPLAY = True
DEBUG = False
psynet.media.LOCAL_S3 = True  # set this to False if you deploy online, so that the stimuli will be stored in S3
NUM_ITERATIONS_PER_CHAIN = DIMENSIONS * 2

NUM_CHAINS_PER_EXPERIMENT = 2
NUM_CHAINS_PER_PARTICIPANT = 2
NUM_TRIALS_PER_PARTICIPANT = 2


class CustomNetwork(VideoGibbsNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    synth_function_location = {
        "module_name": "custom_synth",
        "function_name": "synth_stimulus",
    }

    s3_bucket = "video-gibbs-demo"
    vector_length = DIMENSIONS
    vector_ranges = VECTOR_RANGES
    granularity = GRANULARITY

    n_jobs = 8  # <--- Parallelizes stimulus synthesis into 8 parallel processes at each worker node

    def make_definition(self):
        return {"target": self.balance_across_networks(TARGETS)}


class CustomTrial(VideoGibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = 3.0
    time_estimate = 5.0

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider so that the video is as "
            f"<strong>{self.network.definition['target']}</strong> as possible."
        )


class CustomNode(VideoGibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}


class CustomSource(VideoGibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}


class CustomTrialMaker(VideoGibbsTrialMaker):
    response_timeout_sec = 1e9


trial_maker = CustomTrialMaker(
    id_="video_gibbs_demo",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
    phase="experiment",  # can be whatever you like
    chain_type="across",  # can be "within" or "across"
    num_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
    num_iterations_per_chain=NUM_ITERATIONS_PER_CHAIN,
    num_chains_per_participant=None,  # set to None if chain_type="across"
    num_chains_per_experiment=NUM_CHAINS_PER_EXPERIMENT,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
    check_performance_at_end=False,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_trials",
    target_num_participants=None,
    wait_for_networks=True,
)

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        CAPRecruiterStandardConsent(),
        CAPRecruiterAudiovisualConsent(),
        trial_maker,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)

        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1
