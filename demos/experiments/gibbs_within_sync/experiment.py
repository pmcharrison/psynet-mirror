import random
from typing import List, Union

from dominate import tags
from markupsafe import Markup

import psynet.experiment
from psynet.asset import LocalStorage
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, Prompt, SliderControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.sync import GroupBarrier, SimpleGrouper
from psynet.timeline import PageMaker, Timeline, join
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


class CustomTrial(GibbsTrial):
    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    resample_free_parameter = True
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return join(
            PageMaker(self.choose_response),
            GroupBarrier(
                id_="see_group_responses",
                group_type="gibbs",
            ),
            PageMaker(self.see_group_responses),
        )

    def choose_response(self):
        target = self.context["target"]

        prompt = tags.span()
        with prompt:
            tags.span(
                "Adjust the slider to match the following word as well as possible: "
            )
            tags.strong(target)

        return ColorSliderPage(
            "color_trial",
            prompt,
            starting_values=self.initial_vector,
            selected_idx=self.active_index,
            reverse_scale=self.reverse_scale,
            directional=False,
            time_estimate=5,
        )

    def see_group_responses(self, participant: Participant):
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            "localhost", port=12345, stdoutToServer=True, stderrToServer=True
        )

        participant_response = (
            participant.answer
        )  # this is not actually right, we need to check this
        other_participants = [
            p for p in participant.sync_group.participants if p != participant
        ]
        other_responses = [p.answer for p in other_participants]

        html = tags.span()
        with html:
            tags.p(f"You chose: {participant_response}")
            tags.p("Other participants chose:")
            with tags.ul():
                for response in other_responses:
                    tags.li(response)

        return InfoPage(html, time_estimate=5)


class CustomNode(GibbsNode):
    vector_length = 3

    def random_sample(self, i):
        return random.randint(0, 255)

    def summarize_trials(self, trials: list, experiment, participant):
        # We need to get access to the participants' trials here.
        # Currently they are not available because of the idiosyncratic way
        # that the Barrier works
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            "localhost", port=12345, stdoutToServer=True, stderrToServer=True
        )


trial_maker = GibbsTrialMaker(
    id_="gibbs_demo",
    start_nodes=lambda: [CustomNode(context={"target": random.sample(TARGETS, 1)[0]})],
    network_class=GibbsNetwork,
    sync_group_type="gibbs",
    trial_class=CustomTrial,
    node_class=CustomNode,
    chain_type="within",
    expected_trials_per_participant=4,
    max_trials_per_participant=4,
    max_nodes_per_chain=10,
    chains_per_participant=1,  # set to None if chain_type="across"
    chains_per_experiment=None,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="n_participants",
    target_n_participants=3,
)


class Exp(psynet.experiment.Experiment):
    label = "Gibbs demo"
    asset_storage = LocalStorage()
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        SimpleGrouper(
            group_type="gibbs",
            group_size=3,
        ),
        trial_maker,
        SuccessfulEndPage(),
    )
