import random
from typing import List, Union

from dominate import tags
from markupsafe import Markup

import psynet.experiment
from psynet.bot import Bot, advance_past_wait_pages
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, Prompt, SliderControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.sync import SimpleGrouper
from psynet.timeline import Timeline, join
from psynet.trial.gibbs import GibbsNode, GibbsTrial, GibbsTrialMaker
from psynet.utils import as_plain_text, get_logger

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
        assert 0 <= selected_idx < len(COLORS)
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
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return join(
            self.see_last_trial_responses(participant) if self.degree > 0 else None,
            self.choose_response(),
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

    def see_last_trial_responses(self, participant: Participant):
        last_node = self.node.parent
        last_trials = last_node.all_trials
        last_trials.sort(key=lambda t: t.participant_id)
        participant_answer = [
            t.answer for t in last_trials if t.participant == participant
        ][0]
        other_participant_answers = [
            t.answer for t in last_trials if t.participant != participant
        ]

        html = tags.span()
        with html:
            tags.p(f"You chose: {participant_answer}")
            tags.p("Other participants chose:")
            with tags.ul():
                for response in other_participant_answers:
                    tags.li(response)
            tags.p(
                f"The summarized response was {last_node.var.summarize_trials_output}."
            )

        return InfoPage(html, time_estimate=5)


class CustomNode(GibbsNode):
    vector_length = 3

    def random_sample(self, i):
        return random.randint(0, 255)


trial_maker = GibbsTrialMaker(
    id_="gibbs_demo",
    start_nodes=lambda: [CustomNode(context={"target": random.sample(TARGETS, 1)[0]})],
    sync_group_type="gibbs",
    trial_class=CustomTrial,
    node_class=CustomNode,
    chain_type="within",
    expected_trials_per_participant=4,
    max_trials_per_participant=4,
    max_nodes_per_chain=4,
    chains_per_participant=1,
    recruit_mode="n_participants",
    target_n_participants=3,
)


class Exp(psynet.experiment.Experiment):
    label = "Gibbs within sync demo"
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

    test_n_bots = 3

    def test_serial_run_bots(self, bots: List[Bot]):
        from psynet.page import WaitPage

        advance_past_wait_pages(bots)

        page = bots[0].get_current_page()
        assert page.label == "color_trial"
        bots[0].take_page(page, response=100)
        page = bots[0].get_current_page()
        assert isinstance(page, WaitPage)

        bots[1].take_page(page, response=110)
        bots[2].take_page(page, response=120)

        advance_past_wait_pages(bots)
        page = bots[0].get_current_page()

        assert (
            as_plain_text(page.prompt.text)
            == "You chose: 100 Other participants chose: * 110 * 120 The summarized response was 110."
        )

        for remaining_nodes in range(3):
            for bot in bots:
                page = bot.get_current_page()
                assert isinstance(page, InfoPage)
                bot.take_page(page)

                page = bot.get_current_page()
                assert page.label == "color_trial"
                bot.take_page(page)
            advance_past_wait_pages(bots)

        for bot in bots:
            page = bot.get_current_page()
            text = as_plain_text(page.prompt.text)
            assert "That's the end of the experiment!" in text
