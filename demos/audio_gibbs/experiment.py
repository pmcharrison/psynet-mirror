# pylint: disable=unused-import,abstract-method,unused-argument,no-member

# Note: parselmouth must be installed with pip install praat-parselmouth

##########################################################################################
# Imports
##########################################################################################

from flask import Markup

import psynet.experiment
import psynet.media
from psynet.consent import CAPRecruiterAudiovisualConsent, CAPRecruiterStandardConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.audio_gibbs import (
    AudioGibbsNetwork,
    AudioGibbsNode,
    AudioGibbsSource,
    AudioGibbsTrial,
    AudioGibbsTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


# Custom parameters, change these as you like!
TARGETS = ["critical", "suggestive", "angry"]
DIMENSIONS = 5
RANGE = [-800, 800]
GRANULARITY = 25
SNAP_SLIDER = True
AUTOPLAY = True
DEBUG = False
psynet.media.LOCAL_S3 = True  # set this to False if you deploy online, so that the stimuli will be stored in S3


class CustomNetwork(AudioGibbsNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    synth_function_location = {
        "module_name": "custom_synth",
        "function_name": "synth_stimulus",
    }

    s3_bucket = "audio-gibbs-demo"
    vector_length = DIMENSIONS
    vector_ranges = [RANGE for _ in range(DIMENSIONS)]
    granularity = GRANULARITY

    def make_definition(self):
        return {"target": self.balance_across_networks(TARGETS)}


class CustomTrial(AudioGibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = 3.0

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider so that the word sounds as "
            f"<strong>{self.network.definition['target']}</strong> "
            "as possible."
        )


class CustomNode(AudioGibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}


class CustomSource(AudioGibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}


class CustomTrialMaker(AudioGibbsTrialMaker):
    performance_threshold = -1.0
    give_end_feedback_passed = True

    def get_end_feedback_passed_page(self, score):
        score_to_display = "NA" if score is None else f"{(100 * score):.0f}"

        return InfoPage(
            Markup(
                f"Your consistency score was <strong>{score_to_display}&#37;</strong>."
            ),
            time_estimate=5,
        )


trial_maker = CustomTrialMaker(
    id_="audio_gibbs_demo",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
    phase="experiment",  # can be whatever you like
    time_estimate_per_trial=5,
    chain_type="within",  # can be "within" or "across"
    num_trials_per_participant=21,
    num_iterations_per_chain=7,
    num_chains_per_participant=3,  # set to None if chain_type="across"
    num_chains_per_experiment=None,  # set to None if chain_type="within"
    trials_per_node=1,
    active_balancing_across_chains=True,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_participants",
    target_num_participants=10,
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
