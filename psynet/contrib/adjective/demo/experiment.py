from dallinger.experiment_server.dashboard import dashboard_tab
from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.contrib.adjective.pipeline import AdjectivePipeline
from psynet.modular_page import ModularPage, Prompt, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Module, Timeline, switch
from psynet.utils import get_logger

logger = get_logger()

video_url = [
    "https://mini-kinetics-psy.s3.amazonaws.com/mini-kinetics-validation/cut_videos/[zumba]_dLE5YOEqBGs.mp4"
]

audio_url = [
    "https://mini-kinetics-psy.s3.amazonaws.com/emotional_prosody/03-01-08-02-02-02-24.wav"
]

image_url = [
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/amaranth1.jpg"
]

image_urls = [
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/thaieggplant3.jpg",
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/tomato6.jpg",
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/wintersquash1.jpg",
    "https://s3.amazonaws.com/generalization-datasets/vegetables/images/yellowonion1.jpg",
]


class Exp(psynet.experiment.Experiment):
    # Add a dashboard tab
    @dashboard_tab("Adjective pipeline", after_route="monitoring")
    @classmethod
    def dashboard_tab(cls):
        return psynet.contrib.adjective.pipeline.render_adjective_pipelines_summary(cls)

    timeline = Timeline(
        NoConsent(),
        Module(
            "test",
            ModularPage(
                "test_nafc",
                Prompt("What condition do you want to test?"),
                control=PushButtonControl(
                    ["Single video", "Mixed media practice", "Multiple images"],
                    arrange_vertically=False,
                ),
                time_estimate=5,
            ),
            switch(
                "test_condition",
                lambda participant: participant.answer,
                branches={
                    "Single video": AdjectivePipeline(
                        id_="single_video_trial",
                        media_urls=video_url,
                        num_trials_per_participant=1,
                        base_time_estimate=5,
                        min_iterations=4,
                        phase="experiment",
                        prune_flags=True,
                        new_word_bonus=0.01,
                        upvote_bonus=0.01,
                        show_positive_feedback_every=1,
                        template_args={
                            "stimulus_type_singular": "video clip",
                            "play_duration": 1,
                            "randomize_start": True,
                        },
                    ),
                    "Mixed media practice": AdjectivePipeline(
                        id_="mixed_media_practice_trial",
                        media_urls=image_url + video_url + audio_url,
                        num_trials_per_participant=3,
                        base_time_estimate=4,
                        phase="practice",
                        practice_threshold=0.25,  # consisteny of at least
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
                    # Check:
                    # - Does pruning work?
                    # - Are people kicked out of the experiment if they don't prune?
                    "Multiple images": AdjectivePipeline(
                        id_="experiment_images",
                        media_urls=image_urls,
                        num_trials_per_participant=4,
                        base_time_estimate=4,
                        phase="experiment",
                        prune_flags=True,
                        new_word_bonus=None,
                        upvote_bonus=None,
                        show_positive_feedback_every=0,  # No bonus
                        template_args={"stimulus_type_singular": "vegetable"},
                    ),
                },
                fix_time_credit=False,
            ),
        ),
        SuccessfulEndPage(),
    )
