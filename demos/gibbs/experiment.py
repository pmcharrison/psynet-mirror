# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################

import random
from typing import List, Union

from dallinger import db
from flask import Markup
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

import psynet.experiment
from psynet.consent import NoConsent
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.modular_page import ModularPage, PushButtonControl, SliderControl
from psynet.page import InfoPage, Prompt, SuccessfulEndPage
from psynet.participant import Participant
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


class ColorSliderPage(ModularPage):
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
            label,
            Prompt(prompt),
            control=SliderControl(
                label=label,
                start_value=starting_values[selected_idx],
                min_value=0,
                max_value=255,
                slider_id=COLORS[selected_idx],
                reverse_scale=reverse_scale,
                directional=directional,
                template_filename="color-slider.html",
                template_args={
                    "hidden_inputs": hidden_inputs,
                },
                continuous_updates=False,
            ),
            time_estimate=time_estimate,
        )

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt.metadata,
            "selected_idx": self.selected_idx,
            "starting_values": self.starting_values,
        }


class CustomNetwork(GibbsNetwork):
    vector_length = 3

    def random_sample(self, i):
        return random.randint(0, 255)

    def make_definition(self):
        return {
            "target": self.balance_across_networks(TARGETS),
            "participant_group": self.balance_across_networks(["A", "B"]),
        }


class CustomTrial(GibbsTrial):
    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    resample_free_parameter = True

    time_estimate = 5

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
    pass


class CustomSource(GibbsSource):
    pass


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

    def custom_network_filter(self, candidates, participant):
        # As an example, let's make the participant join networks
        # in order of increasing network ID.
        candidates.sort(key=lambda x: x.id)
        return [candidates[0]]


trial_maker = CustomTrialMaker(
    id_="gibbs_demo",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
    phase="experiment",  # can be whatever you like
    chain_type="across",  # can be "within" or "across"
    num_trials_per_participant=4,
    num_iterations_per_chain=2,
    num_chains_per_participant=None,  # set to None if chain_type="across"
    num_chains_per_experiment=8,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_trials",
    target_num_participants=None,
    num_repeat_trials=3,
)

###################
# This code is borrowed from the custom_table_simple demo.
# It is totally irrelevant for the Gibbs implementation.
# We just include it so we can test the export functionality
# in the regression tests.


@register_table
class Coin(SQLBase, SQLMixin):
    __tablename__ = "coin"

    participant = relationship(Participant, backref="all_coins")
    participant_id = Column(Integer, ForeignKey("participant.id"))

    def __init__(self, participant):
        self.participant = participant
        self.participant_id = participant.id


def collect_coin():
    return CodeBlock(_collect_coin)


def _collect_coin(participant):
    coin = Coin(participant)
    coin.var.test = "123"
    db.session.add(coin)


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "choose_network",
            Prompt("What participant group would you like to join?"),
            control=PushButtonControl(["A", "B"], arrange_vertically=False),
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.set_participant_group(
                "gibbs_demo", participant.answer
            )
        ),
        trial_maker,
        collect_coin(),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)

        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1
