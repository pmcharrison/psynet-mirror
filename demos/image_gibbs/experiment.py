# pylint: disable=unused-import,abstract-method,unused-argument,no-member
import os

from markupsafe import Markup

import psynet.experiment
import psynet.media
from psynet.asset import DebugStorage
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.media_gibbs import (
    ImageGibbsNode,
    ImageGibbsTrial,
    ImageGibbsTrialMaker,
)
from psynet.utils import get_logger, linspace

from . import custom_synth

logger = get_logger()

# Custom parameters, change these as you like!
TARGETS = ["positive", "energetic"]
RGB_RANGE = [0, 255]
VECTOR_RANGES = [
    RGB_RANGE,
    RGB_RANGE,
    RGB_RANGE
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


class CustomTrial(ImageGibbsTrial):
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    debug = DEBUG
    minimal_time = 3.0
    time_estimate = 5.0

    def get_prompt(self, experiment, participant):
        return Markup(
            "<center></br>Adjust the slider so that the image is as "
            f"<strong>{self.context['target']}</strong> "
            "as possible.</center>"
        )


class CustomNode(ImageGibbsNode):
    vector_length = DIMENSIONS
    vector_ranges = VECTOR_RANGES
    granularity = GRANULARITY
    n_jobs = 8  # <--- Parallelizes stimulus synthesis into 8 parallel processes at each worker node

    # If you want to change the image extension to e.g. .png, add this changed prepare_stimuli function:
    # def prepare_stimuli(self, range_to_sample, granularity, output_dir, modality):
    #     logger.info(modality)
    #     assert modality in ["audio", "image", "video"]
    #     match modality:
    #         case "audio":
    #             ext = ".wav"
    #         case "image":
    #             ext = ".png"
    #         case "video":
    #             ext = ".mp4"
    #     values = linspace(range_to_sample[0], range_to_sample[1], granularity)
    #     ids = [f"slider_stimulus_{_i}" for _i, _ in enumerate(values)]
    #     files = [f"{_id}{ext}" for _id in ids]
    #     paths = [os.path.join(output_dir, _file) for _file in files]
    #     stimuli = [
    #         {"id": _id, "value": _value, "path": _path}
    #         for _id, _value, _path in zip(ids, values, paths)
    #     ]
    #     return values, ids, files, paths, stimuli

    def synth_function(self, vector, output_path, chain_definition):
        custom_synth.synth_stimulus(vector, output_path, {})


class CustomTrialMaker(ImageGibbsTrialMaker):
    pass


trial_maker = CustomTrialMaker(
    id_="image_gibbs_demo",
    trial_class=CustomTrial,
    node_class=CustomNode,
    chain_type="across",  # can be "within" or "across"
    expected_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
    max_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
    max_nodes_per_chain=NUM_ITERATIONS_PER_CHAIN,
    start_nodes=lambda: [CustomNode(context={"target": target}) for target in TARGETS],
    chains_per_experiment=NUM_CHAINS_PER_EXPERIMENT,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
    check_performance_at_end=False,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_trials",
    target_n_participants=None,
    wait_for_networks=True,
)


class Exp(psynet.experiment.Experiment):
    label = "Image Gibbs sampling demo"
    asset_storage = DebugStorage()
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        trial_maker,
        SuccessfulEndPage(),
    )

Exp.css_links.append("static/theme.css")