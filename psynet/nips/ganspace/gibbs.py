import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from flask import Markup
from uuid import uuid4

from psynet.timeline import join

from psynet.page import (
    InfoPage
)
from psynet.modular_page import (
    ModularPage,
    VideoSliderControl
)
from psynet.trial.gibbs import (
    GibbsNetwork, GibbsTrial, GibbsNode, GibbsSource, GibbsTrialMaker
)

def gibbs_factory(config):
    targets = config["targets"]

    class CustomNetwork(GibbsNetwork):
        __mapper_args__ = {"polymorphic_identity": "custom_network"}

        vector_length = config["num_dimensions"]

        def random_sample(self, i):
            slider_sigma = config["slider_sigma"]
            lower_bound = - slider_sigma
            upper_bound = slider_sigma
            raw = random.normalvariate(0, 1)
            return min(max(raw, lower_bound), upper_bound)

        def make_definition(self):
            return {
                "target": self.balance_across_networks(targets)
            }

        run_async_post_grow_network = True
        def async_post_grow_network(self):
            import requests
            import json

            logger.info("Making generation request for network %i...)", self.id)

            head = self.head
            filename = f"{uuid4()}.mp4"

            pc_values = [0 for _ in range(70)]
            for i in range(config["num_dimensions"]):
                pc_values[i] = head.vector[i]

            pc_to_manipulate = head.active_index

            response = requests.post(config["ganspace_server"] + "/generate", json={
                "password": "helmholtz-is-cool",
                "bucket": "cap-ganspace",
                "key": filename,
                "args": {
                    "pc_values": pc_values,
                    "pc_to_manipulate": pc_to_manipulate,
                    "sigma_range": config["slider_sigma"],
                    "n_frames": 150,
                    "scale": "350x350",
                    "resample": False,
                    "seed": 0
                }
            })
            info = json.loads(response.content)
            head.var.key = info["key"]
            head.var.url = info["url"]

    class CustomTrial(GibbsTrial):
        __mapper_args__ = {"polymorphic_identity": "custom_trial"}

        # If True, then the starting value for the free parameter is resampled
        # on each trial.
        resample_free_parameter = True

        def show_trial(self, experiment, participant):
            target = self.network.definition["target"]
            prompt = Markup(
                f"""
                <style>
                    .text_prompt {{
                        text-align: center;
                    }}
                </style>
                <div class="text_prompt">
                    <p>
                        Adjust the slider to match the following word as well as possible:
                    </p>
                    <p>
                        <strong>{target}</strong>
                    </p>
                    <p>
                        If moving the slider doesn't make any difference,
                        just put the slider in a central position.
                    </p>
                </div>
                """
            )
            return FaceSliderPage(
                prompt=prompt,
                url=self.origin.var.url,
                reverse_scale=self.reverse_scale,
                start_value = self.initial_vector[self.active_index]
            )

    class FaceSliderPage(ModularPage):
        def __init__(self, prompt, url, reverse_scale, start_value):
            super().__init__(
                "face_slider",
                prompt=prompt,
                control=VideoSliderControl(
                    url=url,
                    file_type="mp4",
                    width="350px",
                    height="350px",
                    reverse_scale=reverse_scale,
                    starting_value=self.from_sigma_scale_to_unit_interval(start_value),
                    minimal_time=5
                )
            )

        def from_unit_interval_to_sigma_scale(self, x):
            return (x - 0.5) * 2 * config["slider_sigma"]

        def from_sigma_scale_to_unit_interval(self, x):
            return (x + config["slider_sigma"]) / (2 * config["slider_sigma"])

        def format_answer(self, raw_answer, **kwargs):
            return self.from_unit_interval_to_sigma_scale(raw_answer)

    class CustomNode(GibbsNode):
        __mapper_args__ = {"polymorphic_identity": "custom_node"}


    class CustomSource(GibbsSource):
        __mapper_args__ = {"polymorphic_identity": "custom_source"}

    class CustomTrialMaker(GibbsTrialMaker):
        give_end_feedback_passed = False
        performance_threshold = -1.0
        async_timeout_sec = 60 * 60 # 1 hour for async processes to time out.
        allow_revisiting_networks_in_across_chains = True

        def compute_bonus(self, score, passed):
            if self.phase == "practice":
                return 0.0
            elif self.phase == "experiment":
                if score is None:
                    return 0.0
                else:
                    return max(0.0, score)
            else:
                raise NotImplementedError


    instructions = join(
        InfoPage(
            """
            In each trial of the main experiment you will be presented with a word,
            and your task will be to choose a face that matches this word.
            You will choose this face using a continuous slider.
            """,
            time_estimate=5
        ),
        InfoPage(
            """
            The quality of your responses will be automatically monitored,
            and you will receive a bonus at the end of the experiment
            in proportion to your quality score. The best way to achieve
            a high score is to concentrate and give each trial your best attempt.
            """,
            time_estimate=5
        )
    )

    return {
        "Network": CustomNetwork,
        "Node": CustomNode,
        "Source": CustomSource,
        "Trial": CustomTrial,
        "TrialMaker": CustomTrialMaker,
        "instructions": instructions
    }
