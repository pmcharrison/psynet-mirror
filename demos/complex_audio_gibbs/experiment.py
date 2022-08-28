# pylint: disable=unused-import,abstract-method,unused-argument,no-member

# Note: parselmouth must be installed with pip install praat-parselmouth

##########################################################################################
# Imports
##########################################################################################

import random

from flask import Markup

import psynet.experiment
import psynet.media
from psynet.asset import DebugStorage
from psynet.bot import Bot
from psynet.consent import CAPRecruiterAudiovisualConsent, CAPRecruiterStandardConsent
from psynet.page import SuccessfulEndPage
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
TARGETS = ["sad", "happy", "angry"]
SENTENCE_RECORDINGS = [
    "Harvard_L35_S01_0.wav",
    "Harvard_L35_S02_0.wav",
    "Harvard_L35_S03_0.wav",
]
RANGES = [
    # DURATION
    # 1. Duration, percent
    [0.8, 1.2],
    # INTENSITY
    # 2. Tremolo rate, st
    [0.01, 5],
    # 3. Tremolo depth, dB
    [0.01, 10],
    # PITCH
    # 4. Shift, semitones
    [-3, 3],
    # 5. Range, percent
    [0.2, 1.8],
    # 6. Increase/Decrease, semitones
    [-3, 3],
    # 7. Jitter, custom unit
    [0, 10],
]
INITIAL_VALUES = [
    1,  # 1. Duration, percent
    0.1,  # 2. Tremolo rate, st
    0.05,  # 3. Tremolo depth, dB
    0,  # 4. Shift, semitones
    1,  # 5. Range, percent
    0,  # 6. Increase/Decrease, semitones
    0,  # 7. Jitter, custom unit
]
DIMENSIONS = len(INITIAL_VALUES)
MIN_DURATION = 5
TIME_ESTIMATE_PER_TRIAL = 5
GRANULARITY = 25
SNAP_SLIDER = False
AUTOPLAY = True
DEBUG = False

NUM_ITERATIONS_PER_CHAIN = DIMENSIONS * 2  # every dimension is visited twice
NUM_CHAINS_PER_EXPERIMENT = (
    len(TARGETS) * 3
)  # for each emotion there are 3 chains (each with a different sentence)
NUM_TRIALS_PER_PARTICIPANT = len(TARGETS) * 3  # every participant does 9 trials


class CustomNetwork(AudioGibbsNetwork):
    synth_function_location = {
        "module_name": "custom_synth",
        "function_name": "synth_stimulus",
    }

    s3_bucket = "audio-gibbs-demo"
    vector_length = DIMENSIONS
    vector_ranges = RANGES
    granularity = GRANULARITY

    n_jobs = 8  # <--- Parallelizes stimulus synthesis into 8 parallel processes at each worker node

    def make_definition(self):
        return {
            "target": self.balance_across_networks(TARGETS),
            "file": random.sample(SENTENCE_RECORDINGS, 1)[0],  # Get random sample
        }


class CustomTrial(AudioGibbsTrial):
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = MIN_DURATION
    time_estimate = TIME_ESTIMATE_PER_TRIAL

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider to make the speaker sound like she is "
            f"<strong>{self.network.definition['target']}</strong>."
        )


class CustomNode(AudioGibbsNode):
    pass


class CustomSource(AudioGibbsSource):
    def generate_seed(self, network, experiment, participant):
        if network.vector_length is None:
            raise ValueError(
                "network.vector_length must not be None. Did you forget to set it?"
            )
        return {
            "vector": INITIAL_VALUES,  # Start at predefined zero points, i.e. not at a random point in space
            "active_index": random.randint(0, network.vector_length),  #
        }


class CustomTrialMaker(AudioGibbsTrialMaker):
    response_timeout_sec = 1e9


trial_maker = CustomTrialMaker(
    id_="audio_gibbs_demo",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
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
    label = "Complex audio Gibbs sampling demo"
    asset_storage = DebugStorage()
    initial_recruitment_size = 1

    timeline = Timeline(
        CAPRecruiterStandardConsent(),
        CAPRecruiterAudiovisualConsent(),
        trial_maker,
        SuccessfulEndPage(),
    )

    test_num_bots = 2

    def test_check_bot(self, bot: Bot):
        assert not bot.failed
        assert len(bot.trials) == NUM_TRIALS_PER_PARTICIPANT
