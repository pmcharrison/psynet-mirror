# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################

import random
from typing import List, Union

from flask import Markup

import psynet.experiment
from psynet.page import InfoPage, NAFCPage, SliderPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline
from psynet.trial.gibbs import (
    GibbsNetwork,
    GibbsNode,
    GibbsSource,
    GibbsTrial,
    GibbsTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()

TARGETS = ["tree", "rock", "carrot", "banana"]
COLORS = ["red", "green", "blue"]


class ColorSliderPage(SliderPage):
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        selected_idx: int,
        starting_values: List[int],
        reverse_scale: bool,
        directional: bool,
        time_estimate=None,
        **kwargs,
    ):
        assert selected_idx >= 0 and selected_idx < len(COLORS)
        self.prompt = prompt
        self.selected_idx = selected_idx
        self.starting_values = starting_values

        not_selected_idxs = list(range(len(COLORS)))
        not_selected_idxs.remove(selected_idx)
        not_selected_colors = [COLORS[i] for i in not_selected_idxs]
        not_selected_values = [starting_values[i] for i in not_selected_idxs]
        hidden_inputs = dict(zip(not_selected_colors, not_selected_values))
        kwargs["template_arg"] = {
            "hidden_inputs": hidden_inputs,
        }
        super().__init__(
            time_estimate=time_estimate,
            template_filename="color-slider.html",
            label=label,
            prompt=prompt,
            start_value=starting_values[selected_idx],
            min_value=0,
            max_value=255,
            slider_id=COLORS[selected_idx],
            reverse_scale=reverse_scale,
            directional=directional,
            template_arg={
                "hidden_inputs": hidden_inputs,
            },
            continuous_updates=True,
        )

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt.metadata,
            "selected_idx": self.selected_idx,
            "starting_values": self.starting_values,
        }


class CustomNetwork(GibbsNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    vector_length = 3

    def random_sample(self, i):
        return random.randint(0, 255)

    def make_definition(self):
        return {
            "target": self.balance_across_networks(TARGETS),
            "participant_group": self.balance_across_networks(["A", "B"]),
        }


class CustomTrial(GibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    resample_free_parameter = True

    def show_trial(self, experiment, participant):
        target = self.network.definition["target"]
        prompt = Markup(
            f"<h3 id='participant-group'>Participant group = {participant.get_participant_group('gibbs_demo')}</h3>"
            "<p>Adjust the slider to match the following word as well as possible: "
            f"<strong>{target}</strong></p>"
        )
        return ColorSliderPage(
            "color_trial",
            prompt,
            starting_values=self.initial_vector,
            selected_idx=self.active_index,
            reverse_scale=self.reverse_scale,
            directional=False,
            time_estimate=5,
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
            Markup(
                f"Your consistency score was <strong>{score_to_display}&#37;</strong>."
            ),
            time_estimate=5,
        )

    def compute_bonus(self, score, passed):
        if score is None:
            return 0.0
        else:
            return max(0.0, score)


trial_maker = CustomTrialMaker(
    id_="gibbs_demo",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
    phase="experiment",  # can be whatever you like
    time_estimate_per_trial=5,
    chain_type="across",  # can be "within" or "across"
    num_trials_per_participant=4,
    num_iterations_per_chain=2,
    num_chains_per_participant=None,  # set to None if chain_type="across"
    num_chains_per_experiment=8,  # set to None if chain_type="within"
    trials_per_node=1,
    active_balancing_across_chains=True,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_trials",
    target_num_participants=None,
    num_repeat_trials=3,
)

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        NAFCPage(
            "choose_network",
            "What participant group would you like to join?",
            ["A", "B"],
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.set_participant_group(
                "gibbs_demo", participant.answer
            )
        ),
        trial_maker,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)

        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1


extra_routes = Exp().extra_routes()
