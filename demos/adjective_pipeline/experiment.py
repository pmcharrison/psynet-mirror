####################################
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# WARNING
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# The adjective pipeline is still under construction. There will be breaking changes from commit to commit. Make
#  sure when using the pipeline you always specify the hash of a specific commit for future reproducibility!
####################################


from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.adjective_pipeline import AdjectivePipeline
from psynet.utils import get_logger

logger = get_logger()

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
practice_video = [
    "https://mini-kinetics-psy.s3.amazonaws.com/mini-kinetics-validation/cut_videos/[zumba]_dLE5YOEqBGs.mp4"
]

practice_audio = [
    "https://mini-kinetics-psy.s3.amazonaws.com/emotional_prosody/03-01-08-02-02-02-24.wav"
]

practice_image = [
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/amaranth1.jpg",
]

experiment_images = [
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/thaieggplant3.jpg",
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/tomato6.jpg",
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/wintersquash1.jpg",
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/yellowonion1.jpg",
    # 'https://s3.amazonaws.com/generalization-datasets/vegetables/images/amaranth2.jpg',
    # 'https://s3.amazonaws.com/generalization-datasets/vegetables/images/amaranth3.jpg',
    # 'https://s3.amazonaws.com/generalization-datasets/vegetables/images/asparagus1.jpg'
]

# TODO
BASE_TIME_ESTIMATE = 1
# BASE_TIME_ESTIMATE = 5


class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        InfoPage(
            "This is a simple show cast of the adjective pipeline.", time_estimate=5
        ),
        # InfoPage(
        #     "First, I'll show how a speech recording trial looks.", time_estimate=5
        # # ),
        # AdjectivePipeline(
        #     id_="single_audio_trial",
        #     media_urls=practice_audio,
        #     num_trials_per_participant=1,
        #     base_time_estimate=5,
        #     phase="experiment",
        #     prune_flags=True,
        #     new_word_bonus=0.01,
        #     upvote_bonus=0.01,
        #     # TODO
        #     show_positive_feedback_every=1,
        #     #show_positive_feedback_every=5,
        #     template_args={"stimulus_type_singular": "speech recording"},
        # ),
        # InfoPage(
        #     "Next, we can have a look at a video. For this particular video, we randomly play 1 second of the clip.",
        #     time_estimate=5,
        # ),
        AdjectivePipeline(
            id_="single_video_trial",
            media_urls=practice_video,
            num_trials_per_participant=1,
            base_time_estimate=5,
            phase="experiment",
            prune_flags=True,
            new_word_bonus=0.01,
            upvote_bonus=0.01,
            # TODO
            show_positive_feedback_every=1,
            # show_positive_feedback_every=5,
            template_args={
                "stimulus_type_singular": "video clip",
                "play_duration": 1,
                "randomize_start": True,
            },
        ),
        # InfoPage(
        #     "For demonstration proposes, we can also prepopulate the chain, to have a look at the tags.",
        #     time_estimate=5,
        # ),
        # AdjectivePipeline(
        #     id_="single_image_trial",
        #     media_urls=practice_image,
        #     num_trials_per_participant=1,
        #     base_time_estimate=BASE_TIME_ESTIMATE,
        #     phase="experiment",
        #     prune_flags=True,
        #     new_word_bonus=0.01,
        #     upvote_bonus=0.01,
        #     show_positive_feedback_every=5,
        #     template_args={"stimulus_type_singular": "vegetable"},
        #     prepopulate_networks=[["leaf", "green"]]
        # ),
        InfoPage(
            "For the future, we can also mix stimuli types and fully customize the instructions to the participant. Now, "
            "we'll do a short practice session with mixed media.",
            time_estimate=5,
        ),
        AdjectivePipeline(
            id_="mixed_media_practice_trial",
            media_urls=practice_image + practice_video + practice_audio,
            num_trials_per_participant=3,
            base_time_estimate=BASE_TIME_ESTIMATE,
            phase="practice",
            practice_threshold=0.25,
            template_args={
                "play_duration": 3,
                "initial_instruction": Markup(
                    """
                <h3 for="new_tags">CUSTOM INSTRUCTION</h3>
                <div class="alert alert-danger" role="alert">
                <strong>This is a custom instruction, when if can only create tags</strong>
                </div>
                """
                ),
                "later_instruction": Markup(
                    """
                <h3 for="new_tags">NEW INSTRUCTION</h3>
                <div class="alert alert-danger" role="alert">
                <strong>This is another custom instruction, if you can ALSO rate tags</strong>
                </div>
                """
                ),
            },
            prepopulate_networks=[
                ["leaf", "green", "red", "yellow", "brown", "orange"],
                ["dance", "females"],
                ["female", "speech", "emotional"],
            ],
        ),
        InfoPage(
            Markup(
                """
            <div class="alert alert-success" role="alert">
                You passed the practice trial
            </div><br><br>
            Finally, this is what a real experiment would look like.
            """
            ),
            time_estimate=5,
        ),
        AdjectivePipeline(
            id_="experiment_images",
            media_urls=experiment_images,
            num_trials_per_participant=4,
            base_time_estimate=BASE_TIME_ESTIMATE,
            phase="experiment",
            prune_flags=True,
            new_word_bonus=0.01,
            upvote_bonus=0.01,
            show_positive_feedback_every=5,
            template_args={"stimulus_type_singular": "vegetable"},
        ),
        SuccessfulEndPage(),
    )
