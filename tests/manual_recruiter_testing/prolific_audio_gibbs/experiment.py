# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import json
from typing import List

from markupsafe import Markup

import psynet.experiment
import psynet.media
from psynet.asset import LocalStorage
from psynet.bot import Bot
from psynet.demography.general import ExperimentFeedback, HearingLoss
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import HugginsHeadphoneTest
from psynet.timeline import Timeline
from psynet.trial.audio_gibbs import (
    AudioGibbsNode,
    AudioGibbsTrial,
    AudioGibbsTrialMaker,
)
from psynet.utils import get_logger

from . import custom_synth
from .customconsent import CustomMainConsent

logger = get_logger()

# Custom parameters, change these as you like!
TARGETS = ["dominant", "trustworthy"]
DIMENSIONS = 7
RANGE = [-800, 800]
GRANULARITY = 25
SNAP_SLIDER = True
AUTOPLAY = True
DEBUG = False
NUM_ITERATIONS_PER_CHAIN = (
    2  # In a real experiment we'd make this something like DIMENSIONS * 2
)
CHAINS_PER_PARTICIPANT = len(TARGETS)
NUM_TRIALS_PER_PARTICIPANT = NUM_ITERATIONS_PER_CHAIN * CHAINS_PER_PARTICIPANT


class CustomTrial(AudioGibbsTrial):
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = 3.0
    time_estimate = 7.0

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider so that the word sounds as "
            f"<strong>{self.context['target']}</strong> "
            "as possible."
        )


class CustomNode(AudioGibbsNode):
    vector_length = DIMENSIONS
    vector_ranges = [RANGE for _ in range(DIMENSIONS)]
    granularity = GRANULARITY
    n_jobs = 8  # <--- Parallelizes stimulus synthesis into 8 parallel processes at each worker node

    def synth_function(self, vector, output_path, chain_definition):
        custom_synth.synth_stimulus(vector, output_path, chain_definition)


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
    trial_class=CustomTrial,
    node_class=CustomNode,
    chain_type="within",  # can be "within" or "across"
    expected_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
    max_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
    max_nodes_per_chain=NUM_ITERATIONS_PER_CHAIN,
    start_nodes=lambda: [CustomNode(context={"target": target}) for target in TARGETS],
    chains_per_experiment=None,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
    check_performance_at_end=False,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="n_participants",
    target_n_participants=10,
    wait_for_networks=True,
    n_repeat_trials=1,
)


def get_prolific_settings():
    with open("qualification_prolific_en.json", "r") as f:
        qualification = json.dumps(json.load(f))

    return {
        "recruiter": "prolific",
        "base_payment": 0.42,
        "prolific_estimated_completion_minutes": 3,
        "prolific_recruitment_config": qualification,
        "auto_recruit": False,
        "currency": "£",
        "wage_per_hour": 10,
    }


##########################################################################################
# Experiment
##########################################################################################
class Exp(psynet.experiment.Experiment):
    label = "Audio game - play with sounds."
    asset_storage = LocalStorage()
    config = {
        **get_prolific_settings(),
        "initial_recruitment_size": 5,
        "force_incognito_mode": False,
        "title": "Sound game: play with sounds (Chrome browser, Headphones required ~3 min)",
        "description": "A short sound game. Requires a Chrome browser and headphones. The game lasts approximately 3 minutes.",
        "contact_email_on_error": "computational.audition@gmail.com",
        "organization_name": "Max Planck Institute for Empirical Aesthetics",
        "show_reward": False,
    }

    timeline = Timeline(
        CustomMainConsent(),  # since we have 0 wage per hour so we need to delete this.
        HugginsHeadphoneTest(performance_threshold=0),
        trial_maker,
        HearingLoss(),
        ExperimentFeedback(),
        SuccessfulEndPage(),
    )

    test_n_bots = 2

    def test_bots_ran_successfully(self, bots: List[Bot], **kwargs):
        super().test_bots_ran_successfully(bots, **kwargs)

        for b in bots:
            assert len(b.alive_trials) == NUM_TRIALS_PER_PARTICIPANT
