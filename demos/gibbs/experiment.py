# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################

import random
import tempfile
import time
from typing import List, Union

from dallinger import db
from flask import Markup
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

import psynet.experiment
from psynet.asset import DebugStorage, ExperimentAsset
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.demography.general import ExperimentFeedback
from psynet.modular_page import ModularPage, PushButtonControl, SliderControl
from psynet.page import InfoPage, Prompt, SuccessfulEndPage
from psynet.participant import Participant
from psynet.process import AsyncProcess
from psynet.timeline import CodeBlock, Timeline
from psynet.trial.gibbs import GibbsNetwork, GibbsNode, GibbsTrial, GibbsTrialMaker
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
                bot_response=lambda: random.randint(0, 255),
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
    run_async_post_grow_network = True

    # TODO - migrate this to start_nodes
    def make_definition(self):
        return {
            "target": self.balance_across_networks(TARGETS),
            "participant_group": self.balance_across_networks(["A", "B"]),
        }

    def async_post_grow_network(self):
        from psynet.field import UndefinedVariableError

        try:
            self.var.growth_counter += 1
        except UndefinedVariableError:
            self.var.growth_counter = 1


class CustomTrial(GibbsTrial):
    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    run_async_post_trial = True
    resample_free_parameter = True
    time_estimate = 5

    def show_trial(self, experiment, participant):
        target = self.network.definition["target"]
        prompt = Markup(
            f"<h3 id='participant-group'>Participant group = {participant.get_participant_group('gibbs_demo')}</h3>"
            "<p>Adjust the slider to match the following word as well as possible: "
            f"<strong>{target}</strong></p>"
        )
        page = ColorSliderPage(
            "color_trial",
            prompt,
            starting_values=self.initial_vector,
            selected_idx=self.active_index,
            reverse_scale=self.reverse_scale,
            directional=False,
            time_estimate=5,
        )
        return [
            page,
            # You can also include code blocks within a trial.
            # This one doesn't do anything useful, it's just there for demonstration purposes.
            CodeBlock(lambda participant: participant.var.set("test_variable", 123)),
        ]

    def async_post_trial(self):
        # You could put a time-consuming analysis here, perhaps one that generates a plot...
        time.sleep(1)
        self.var.async_post_trial_completed = True
        with tempfile.NamedTemporaryFile("w") as file:
            file.write(f"completed async_post_trial for trial {self.id}")
            asset = ExperimentAsset(
                label="async_post_trial",
                input_path=file.name,
                extension=".txt",
                parent=self,
            )
            asset.deposit()


class CustomNode(GibbsNode):
    vector_length = 3

    def random_sample(self, i):
        return random.randint(0, 255)


class CustomTrialMaker(GibbsTrialMaker):
    give_end_feedback_passed = True
    performance_threshold = -1.0

    # If we set this to True, then the performance check will wait until all async_post_trial processes have finished
    end_performance_check_waits = False

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
        return sorted(candidates, key=lambda x: x.id)


trial_maker = CustomTrialMaker(
    id_="gibbs_demo",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
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
    wait_for_networks=True,  # wait for asynchronous processes to complete before continuing to the next trial
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
    label = "Gibbs demo"
    asset_storage = DebugStorage()
    initial_recruitment_size = 1

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
        ExperimentFeedback(),
        SuccessfulEndPage(),
    )

    test_num_bots = 4

    def test_check_bots(self, bots: List[Bot]):
        time.sleep(2.0)
        for b in bots:
            assert all([t.finalized for t in b.trials])

        processes = AsyncProcess.query.all()
        assert all([not p.failed for p in processes])

        super().test_check_bots(bots)
