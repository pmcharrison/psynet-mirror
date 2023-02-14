# pylint: disable=unused-import,abstract-method,unused-argument,no-member
import math
import urllib
from random import sample

import numpy as np
from flask import Markup

import psynet.experiment
import psynet.media
from psynet.asset import DebugStorage
from psynet.consent import NoConsent
from psynet.modular_page import ImagePrompt, ModularPage
from psynet.page import SuccessfulEndPage
from psynet.timeline import MediaSpec, Timeline
from psynet.trial.audio_gibbs import (
    AudioGibbsNode,
    AudioGibbsTrial,
    AudioGibbsTrialMaker,
)
from psynet.trial.create_and_rate import (
    CreateAndRateNode,
    CreateAndRateTrial,
    CreateAndRateTrialMaker,
    RateControl,
    SelectControl,
)
from psynet.utils import get_logger

from . import custom_synth

# Note: parselmouth must be installed with pip install praat-parselmouth

##########################################################################################
# Imports
##########################################################################################


logger = get_logger()

# Custom parameters, change these as you like!
DIMENSIONS = 7
RANGE = [-800, 800]
GRANULARITY = 25
SNAP_SLIDER = True
AUTOPLAY = True
DEBUG = False
psynet.media.LOCAL_S3 = True  # set this to False if you deploy online, so that the stimuli will be stored in S3
AUDIO_DURATION = 0.75


def readlines(filename):
    with open(filename, "r") as f:
        lines = f.readlines()
    return [line.replace("\n", "") for line in lines]


# Make sure all images are used
main_experiment_urls = [
    "static/" + urllib.parse.quote(file) for file in readlines("robot_names.txt")
]

NUM_TRIALS_PER_PARTICIPANT = 3
NUM_ITERATIONS_PER_CHAIN = 2

INCLUDE_PREVIOUS_ITERATION = True
CREATE_TRIALS = 1
RATE_TRIALS = 1 + INCLUDE_PREVIOUS_ITERATION
TRIALS_PER_NODE = CREATE_TRIALS + RATE_TRIALS


def find_nearest(array, value):
    idx = np.searchsorted(array, value, side="left")
    if idx > 0 and (
        idx == len(array)
        or math.fabs(value - array[idx - 1]) < math.fabs(value - array[idx])
    ):
        return array[idx - 1]
    else:
        return array[idx]


class CustomCreateAndRateTrial(AudioGibbsTrial, CreateAndRateTrial):
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = 3.0
    time_estimate = 5.0

    def get_prompt(self, experiment, participant, is_rate_trial=False):
        prompt = """
                <style>
                    #prompt-text {
                        text-align: center;
                        font-size: 1.5em;
                    }
                    #prompt-image, .prompt_img {
                        image-rendering: -moz-crisp-edges; /* Firefox */
                        image-rendering: -o-crisp-edges; /* Opera */
                        image-rendering: -webkit-optimize-contrast; /* Webkit (non-standard naming) */
                        image-rendering: crisp-edges;
                        -ms-interpolation-mode: nearest-neighbor; /* IE (non-standard property) */
                        width: 100%;
                        max-width: 350px;
                        max-height: 350px;
                    }
                </style>
                """
        if is_rate_trial:
            prompt += "How well does the voice match the robot?"
        else:
            prompt += (
                "Adjust the slider to make the voice match the robot as best as you can"
            )
        return ImagePrompt(self.context["img_url"], Markup(prompt), width="", height="")

    @staticmethod
    def get_previous_iteration(trial):
        definition = trial.origin.definition
        vector = definition["vector"]
        active_index = definition["active_index"]
        return vector[active_index]

    def show_create_trial(self, experiment, participant):
        return super().show_trial(experiment, participant)

    def show_rate_trial(self, experiment, participant):
        ranges = RANGE
        possible_values = list(np.linspace(ranges[0], ranges[1], GRANULARITY))
        creations_to_validate = self.var.get("creations_to_validate")
        assert len(creations_to_validate) == 1
        observation = creations_to_validate[0]
        slider_idx = possible_values.index(find_nearest(possible_values, observation))
        slider_key = f"slider_stimulus_{slider_idx}"
        events, progress_display = self.autoplay_media(
            "audio", [slider_key], media_duration=AUDIO_DURATION
        )
        return ModularPage(
            "rating",
            self.get_prompt(experiment, participant, is_rate_trial=True),
            control=RateControl(
                choices=[5, 4, 3, 2, 1],
                labels=[
                    "Excellent match",
                    "Good match",
                    "Fair match",
                    "Poor match",
                    "Bad match",
                ],
                arrange_vertically=False,
            ),
            media=MediaSpec(audio={"batch": self.media.audio["slider_stimuli"]}),
            events=events,
            progress_display=progress_display,
            time_estimate=5,  # TODO
        )

    def show_trial(self, experiment, participant):
        is_creator = super().is_create_trial()
        if is_creator:
            return self.show_create_trial(experiment, participant)
        else:

            return self.show_rate_trial(experiment, participant)


class CustomCreateAndSelectTrial(CustomCreateAndRateTrial):
    def show_rate_trial(self, experiment, participant):
        ranges = RANGE
        possible_values = list(np.linspace(ranges[0], ranges[1], GRANULARITY))
        creations_to_validate = self.var.get("creations_to_validate")
        trial_maker = self.trial_maker
        expected_creations_to_validate = trial_maker.num_creators + int(
            trial_maker.include_previous_iteration
        )
        assert len(creations_to_validate) == expected_creations_to_validate
        slider_keys = []
        for observation in creations_to_validate:
            slider_idx = possible_values.index(
                find_nearest(possible_values, observation)
            )
            slider_key = f"slider_stimulus_{slider_idx}"
            slider_keys.append(slider_key)

        slider_keys = list(set(slider_keys))  # remove duplicates
        reorder_list = sample(
            list(range(expected_creations_to_validate)), expected_creations_to_validate
        )
        self.var.set("reorder_list", reorder_list)
        events, progress_display = self.autoplay_media(
            "audio",
            slider_keys,
            media_duration=AUDIO_DURATION,
            reorder_list=reorder_list,
        )

        return ModularPage(
            "selection",
            self.get_prompt(experiment, participant, is_rate_trial=True),
            control=SelectControl(reorder_list=reorder_list, arrange_vertically=False),
            media=MediaSpec(audio={"batch": self.media.audio["slider_stimuli"]}),
            events=events,
            progress_display=progress_display,
            time_estimate=5,  # TODO
        )


class CustomNode(AudioGibbsNode, CreateAndRateNode):
    vector_length = DIMENSIONS
    vector_ranges = [RANGE for _ in range(DIMENSIONS)]
    granularity = GRANULARITY
    n_jobs = 8  # <--- Parallelizes stimulus synthesis into 8 parallel processes at each worker node

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CreateAndRateNode.__init__(self)

    def synth_function(self, vector, output_path):
        custom_synth.synth_stimulus(vector, output_path)

    def summarize_trials(self, trials: list, experiment, participant):
        creation = super().get_next_creation(trials)
        if isinstance(creation, CustomNode):
            # is previous iteration
            return creation.definition
        else:
            active_index = trials[0].active_index
            vector = trials[0].updated_vector.copy()
            vector[active_index] = creation.answer
            return {"vector": vector, "active_index": active_index}


start_nodes = [
    CustomNode(
        context={
            "img_url": url,
        }
    )
    for url in main_experiment_urls
]


class CustomCreateAndRateTrialMaker(AudioGibbsTrialMaker, CreateAndRateTrialMaker):
    num_creators = CREATE_TRIALS
    num_raters = RATE_TRIALS
    include_previous_iteration = True

    def __init__(self, *args, **kwargs):
        kwargs["trials_per_node"] = self.num_creators + self.num_raters
        super().__init__(*args, **kwargs)
        CreateAndRateTrialMaker.__init__(self, id_=kwargs["id_"])

    def finalize_trial(self, answer, trial, experiment, participant):
        self.store_visited_networks(trial, participant)

    def find_networks(self, participant, experiment):
        # Obtain available networks
        networks = super().find_networks(
            participant, experiment, return_one_network=False
        )
        return super().filter_networks(
            networks, participant, allow_revisit_with_different_role=True
        )


class CustomCreateAndSelectTrialMaker(CustomCreateAndRateTrialMaker):
    rate_mode = "select"


def make_trial_maker(paradigm_type):
    if paradigm_type == "create_and_rate":
        nodes = [start_nodes[0]]
        trial_class = CustomCreateAndRateTrial
        trial_maker_class = CustomCreateAndRateTrialMaker
    elif paradigm_type == "create_and_select":
        nodes = [start_nodes[1]]
        trial_class = CustomCreateAndSelectTrial
        trial_maker_class = CustomCreateAndSelectTrialMaker
    else:
        raise ValueError("Invalid type")

    return trial_maker_class(
        id_=paradigm_type + "_trial_maker",
        trial_class=trial_class,
        node_class=CustomNode,
        chain_type="across",
        start_nodes=nodes,
        expected_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
        max_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
        max_nodes_per_chain=NUM_ITERATIONS_PER_CHAIN,
        chains_per_experiment=None,  # set to None if chain_type="within"
        balance_across_chains=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        propagate_failure=False,
        recruit_mode="n_trials",
        target_n_participants=None,
        wait_for_networks=False,
        allow_revisiting_networks_in_across_chains=True,
    )


##########################################################################################
# Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    label = "Robot Voice demo"
    asset_storage = DebugStorage()
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        make_trial_maker("create_and_rate"),
        # make_trial_maker("create_and_select"),
        SuccessfulEndPage(),
    )
