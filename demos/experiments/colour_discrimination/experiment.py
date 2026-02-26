import random

from markupsafe import Markup

import psynet.experiment
from psynet.bot import Bot
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage
from psynet.timeline import Event, Timeline
from psynet.trial.staircase import (
    GeometricStaircaseChain,
    GeometricStaircaseNode,
    GeometricStaircaseTrial,
    GeometricStaircaseTrialMaker,
)

chain_definitions = [
    {
        "label": "Low saturation",
        "reference_hue": 220.0,
        "saturation": 45.0,
        "lightness": 56.0,
    },
    {
        "label": "High saturation",
        "reference_hue": 220.0,
        "saturation": 85.0,
        "lightness": 56.0,
    },
]

start_parameter = 24.0
chain_length = 16
max_reversals_per_chain = 4
n_chains = len(chain_definitions)


def get_start_nodes(participant):
    del participant
    return [
        ColourDiscriminationNode(
            parameter=start_parameter,
            context=chain_definition,
            block=str(i),
        )
        for i, chain_definition in enumerate(chain_definitions)
    ]


class ColourDiscriminationNode(GeometricStaircaseNode):
    k = 2
    step = 0.75
    min_parameter = 1.5
    max_parameter = 45.0

    def increase_difficulty(self, parameter):
        return max(self.min_parameter, parameter * self.step)

    def decrease_difficulty(self, parameter):
        return min(self.max_parameter, parameter / self.step)


class ColourDiscriminationTrial(GeometricStaircaseTrial):
    time_estimate = 4

    bot_thresholds = {
        "Low saturation": 12.0,
        "High saturation": 7.5,
    }

    @staticmethod
    def make_hsl(hue, saturation, lightness):
        return f"hsl({hue:.2f}, {saturation:.1f}%, {lightness:.1f}%)"

    def finalize_definition(self, definition, experiment, participant):
        del experiment, participant
        parameter = float(definition["parameter"])
        answer_choices = ["Left is different", "Right is different"]
        correct_answer = random.choice(answer_choices)

        reference_hue = self.context["reference_hue"]
        different_hue = reference_hue + parameter
        saturation = self.context["saturation"]
        lightness = self.context["lightness"]

        reference_color = self.make_hsl(reference_hue, saturation, lightness)
        different_color = self.make_hsl(different_hue, saturation, lightness)

        left_color = different_color if correct_answer == "Left is different" else reference_color
        right_color = (
            different_color if correct_answer == "Right is different" else reference_color
        )

        definition.update(
            {
                "correct_answer": correct_answer,
                "reference_color": reference_color,
                "left_color": left_color,
                "right_color": right_color,
                "difference_degrees": parameter,
            }
        )

        return definition

    def build_prompt(self):
        swatch_style = (
            "width: 175px; height: 175px; border-radius: 14px; border: 1px solid #c7c7c7; "
            "box-shadow: 0 3px 12px rgba(0, 0, 0, 0.12);"
        )
        return Markup(
            f"""
            <div style="max-width: 940px; margin: 0 auto;">
                <p style="font-size: 1.05rem; margin-bottom: 0.75rem;">
                    Select the side whose colour is different from the reference.
                </p>
                <p class="text-muted" style="margin-bottom: 1.1rem;">
                    Condition: <strong>{self.context["label"]}</strong>
                </p>
                <div style="display: flex; justify-content: center; margin-bottom: 1.5rem;">
                    <div style="text-align: center;">
                        <div style="{swatch_style} background: {self.definition["reference_color"]};"></div>
                        <p style="margin-top: 0.5rem; margin-bottom: 0;">Reference</p>
                    </div>
                </div>
                <div style="display: flex; justify-content: center; gap: 4.5rem;">
                    <div style="text-align: center;">
                        <div style="{swatch_style} background: {self.definition["left_color"]};"></div>
                        <p style="margin-top: 0.5rem; margin-bottom: 0;">Left</p>
                    </div>
                    <div style="text-align: center;">
                        <div style="{swatch_style} background: {self.definition["right_color"]};"></div>
                        <p style="margin-top: 0.5rem; margin-bottom: 0;">Right</p>
                    </div>
                </div>
            </div>
            """
        )

    def show_trial(self, experiment, participant):
        del experiment, participant
        return ModularPage(
            "colour_discrimination_trial",
            self.build_prompt(),
            PushButtonControl(
                choices=["Left is different", "Right is different"],
                arrange_vertically=False,
                bot_response=self.get_bot_response,
            ),
            time_estimate=self.time_estimate,
        )

    def show_feedback(self, experiment, participant):
        del experiment, participant
        if self.score == 1:
            feedback = '<p style="color: #157347; font-size: 1.15rem; margin: 0;">Correct!</p>'
        else:
            feedback = (
                '<p style="color: #b02a37; font-size: 1.15rem; margin: 0;">'
                "Incorrect."
                "</p>"
            )

        return ModularPage(
            "colour_discrimination_feedback",
            Markup(feedback),
            events={
                "nextPage": Event(
                    is_triggered_by="submitEnable",
                    delay=0.4,
                    js="psynet.nextPage()",
                )
            },
            show_next_button=False,
            time_estimate=0,
        )

    def get_bot_response(self, bot: Bot):
        del bot
        bot_threshold = self.bot_thresholds[self.context["label"]]
        responds_correctly = self.parameter >= bot_threshold
        if responds_correctly:
            return self.definition["correct_answer"]

        if self.definition["correct_answer"] == "Left is different":
            return "Right is different"
        return "Left is different"

    def score_answer(self, answer, definition):
        return int(answer == definition["correct_answer"])


class ColourDiscriminationTrialMaker(GeometricStaircaseTrialMaker):
    give_end_feedback_passed = True

    def get_end_feedback_passed_page(self, score):
        if score is None:
            threshold_summary = "Threshold could not be estimated."
        else:
            threshold_summary = (
                "Estimated colour discrimination threshold: "
                f"<strong>{score:.2f}&deg;</strong> hue difference."
            )
        return InfoPage(Markup(threshold_summary), time_estimate=5)


class Exp(psynet.experiment.Experiment):
    label = "Colour discrimination staircase demo"

    timeline = Timeline(
        InfoPage(
            """
            In each trial you will see a reference colour and two choice colours.
            One choice colour is identical to the reference and the other is different.
            Select the side that is different.
            """,
            time_estimate=6,
        ),
        ColourDiscriminationTrialMaker(
            id_="colour_discrimination",
            trial_class=ColourDiscriminationTrial,
            node_class=ColourDiscriminationNode,
            start_nodes=get_start_nodes,
            max_nodes_per_chain=chain_length,
            max_reversals_per_chain=max_reversals_per_chain,
            expected_trials_per_participant=n_chains * chain_length,
            target_n_participants=1,
        ),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        del kwargs
        step = ColourDiscriminationNode.step

        chains = GeometricStaircaseChain.query.filter_by(participant_id=bot.id).all()
        assert len(chains) == len(chain_definitions)
        chains.sort(key=lambda chain: chain.head.id)

        for chain_1, chain_2 in zip(chains[:-1], chains[1:]):
            assert min(t.id for t in chain_2.all_trials) > max(
                t.id for t in chain_1.all_trials
            ), "staircase chains were unexpectedly interleaved"

        for chain in chains:
            label = chain.context["label"]
            bot_threshold = ColourDiscriminationTrial.bot_thresholds[label]
            last_trials = sorted(chain.all_trials, key=lambda trial: trial.id)[-4:]
            last_parameters = [trial.definition["parameter"] for trial in last_trials]

            for parameter in last_parameters:
                assert bot_threshold * step <= parameter <= bot_threshold / step, (
                    f"Procedure did not converge to bot threshold for {label} "
                    f"(chain ID = {chain.id}, parameters = {last_parameters}, "
                    f"threshold = {bot_threshold})"
                )

            assert chain.mean_reversal_score is not None
            assert (
                bot_threshold * step
                <= chain.mean_reversal_score
                <= bot_threshold / step
            ), f"Mean reversal score seems incorrect: {chain.mean_reversal_score}"
