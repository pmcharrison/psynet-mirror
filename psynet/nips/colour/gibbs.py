import random

from .colour_slider import ColorSliderPage
from flask import Markup

from psynet.timeline import join

from psynet.page import (
    InfoPage
)
from psynet.trial.gibbs import (
    GibbsNetwork, GibbsTrial, GibbsNode, GibbsSource, GibbsTrialMaker
)

def gibbs_factory(config):
    targets = config["targets"]

    class CustomNetwork(GibbsNetwork):
        __mapper_args__ = {"polymorphic_identity": "custom_network"}

        vector_length = 3

        def random_sample(self, i):
            return random.randint(0, 255)

        def make_definition(self):
            return {
                "target": self.balance_across_networks(targets)
            }

    class CustomTrial(GibbsTrial):
        __mapper_args__ = {"polymorphic_identity": "custom_trial"}

        # If True, then the starting value for the free parameter is resampled
        # on each trial.
        resample_free_parameter = True

        def show_trial(self, experiment, participant):
            target = self.network.definition["target"]
            prompt = Markup(
                "Adjust the slider to match the following word as well as possible: "
                f"<strong>{target}</strong>"
            )
            return ColorSliderPage(
                "color_trial",
                prompt,
                starting_values=self.initial_vector,
                selected_idx=self.active_index,
                reverse_scale=self.reverse_scale,
                time_estimate=5
            )

    class CustomNode(GibbsNode):
        __mapper_args__ = {"polymorphic_identity": "custom_node"}


    class CustomSource(GibbsSource):
        __mapper_args__ = {"polymorphic_identity": "custom_source"}

    class CustomTrialMaker(GibbsTrialMaker):
        give_end_feedback_passed = True
        performance_threshold = -1.0

        def get_end_feedback_passed_page(self, score):
            score_to_display = "NA" if score is None else f"{(100 * score):.0f}"

            return InfoPage(
                Markup(f"Your consistency score was <strong>{score_to_display}&#37;</strong>."),
                time_estimate=5
            )

        def compute_bonus(self, score, passed):
            return max(0.0, score)

    instructions = join(
        InfoPage(
            """
            In each trial of this experiment you will be presented with a word,
            and your task will be to choose a colour that matches this word.
            You will choose this colour using a continuous slider.
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
