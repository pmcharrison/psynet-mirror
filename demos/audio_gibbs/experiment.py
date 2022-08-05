# pylint: disable=unused-import,abstract-method,unused-argument,no-member

# Note: parselmouth must be installed with pip install praat-parselmouth

##########################################################################################
# Imports
##########################################################################################

from typing import List

from flask import Markup

import psynet.experiment
import psynet.media
from psynet.asset import DebugStorage
from psynet.bot import Bot
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
TARGETS = ["dominant", "trustworthy"]
DIMENSIONS = 7
RANGE = [-800, 800]
GRANULARITY = 25
SNAP_SLIDER = True
AUTOPLAY = True
DEBUG = False
psynet.media.LOCAL_S3 = True  # set this to False if you deploy online, so that the stimuli will be stored in S3
NUM_ITERATIONS_PER_CHAIN = DIMENSIONS * 2
NUM_CHAINS_PER_PARTICIPANT = len(TARGETS)
NUM_TRIALS_PER_PARTICIPANT = NUM_ITERATIONS_PER_CHAIN * NUM_CHAINS_PER_PARTICIPANT

assert NUM_TRIALS_PER_PARTICIPANT == 2 * 7 * 2


class CustomNetwork(AudioGibbsNetwork):
    synth_function_location = {
        "module_name": "custom_synth",
        "function_name": "synth_stimulus",
    }

    s3_bucket = "audio-gibbs-demo"
    vector_length = DIMENSIONS
    vector_ranges = [RANGE for _ in range(DIMENSIONS)]
    granularity = GRANULARITY

    n_jobs = 8  # <--- Parallelizes stimulus synthesis into 8 parallel processes at each worker node

    def make_definition(self):
        return {"target": self.balance_across_networks(TARGETS)}


class CustomTrial(AudioGibbsTrial):
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = 3.0
    time_estimate = 5.0

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider so that the word sounds as "
            f"<strong>{self.network.definition['target']}</strong> "
            "as possible."
        )


class CustomNode(AudioGibbsNode):
    pass


class CustomSource(AudioGibbsSource):
    pass


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
    chain_type="within",  # can be "within" or "across"
    num_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
    num_iterations_per_chain=NUM_ITERATIONS_PER_CHAIN,
    num_chains_per_participant=NUM_CHAINS_PER_PARTICIPANT,  # set to None if chain_type="across"
    num_chains_per_experiment=None,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
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
    label = "Audio Gibbs sampling demo"
    asset_storage = DebugStorage()
    initial_recruitment_size = 1

    timeline = Timeline(
        CAPRecruiterStandardConsent(),
        CAPRecruiterAudiovisualConsent(),
        trial_maker,
        SuccessfulEndPage(),
    )

    test_num_bots = 2

    def test_bots_ran_successfully(self, bots: List[Bot], **kwargs):
        super().test_bots_ran_successfully(bots, **kwargs)

        for b in bots:
            assert len(b.trials()) == NUM_TRIALS_PER_PARTICIPANT
