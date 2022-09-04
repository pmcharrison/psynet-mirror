# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging
import random

from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

from . import test_imports  # noqa  (this is for PsyNet's regression tests)

##########################################################################################
# Stimuli
##########################################################################################

nodes = [
    StaticNode(
        definition={"animal": animal},
        block=block,
    )
    for animal in ["cats", "dogs", "fish", "ponies"]
    for block in ["A", "B", "C"]
]


class AnimalTrial(StaticTrial):
    time_estimate = 3

    def finalize_definition(self, definition, experiment, participant):
        definition["text_color"] = random.choice(["red", "green", "blue"])
        return definition

    def show_trial(self, experiment, participant):
        text_color = self.definition["text_color"]
        animal = self.definition["animal"]
        block = self.block

        header = f"<h4 id='trial-position'>Trial {self.position + 1}</h3>"

        if self.is_repeat_trial:
            header = (
                header
                + f"<h4>Repeat trial {self.repeat_trial_index + 1} out of {self.n_repeat_trials}</h3>"
            )
        else:
            header = header + f"<h4>Block {block}</h3>"

        page = ModularPage(
            "animal_trial",
            Markup(
                f"""
                {header}
                <p id='question' style='color: {text_color}'>How much do you like {animal}?</p>
                """
            ),
            PushButtonControl(
                ["Not at all", "A little", "Very much"],
                bot_response="Very much",
            ),
            time_estimate=self.time_estimate,
        )

        return page

    # def show_feedback(self, experiment, participant):
    #     return InfoPage(f"You responded '{self.answer}'.")

    def score_answer(self, answer, definition):
        if answer == "Not at all":
            return 0.0
        return 1.0

    def compute_bonus(self, score):
        # Here we give the participant 1 cent per point immediately after each trial.
        return 0.01 * score


class AnimalTrialMaker(StaticTrialMaker):
    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        failed = False
        for trial in participant_trials:
            if trial.answer == "Not at all":
                failed = True
            else:
                score += 1
        return {"score": score, "passed": not failed}

    def compute_bonus(self, score, passed):
        # At the end of the trial maker, we give the participant 1 dollar for each point.
        # This is combined with their trial-level performance bonus to give their overall performance bonus.
        return 1.0 * score

    give_end_feedback_passed = True

    def get_end_feedback_passed_page(self, score):
        return InfoPage(
            Markup(f"You finished the animal questions! Your score was {score}."),
            time_estimate=5,
        )

    def custom_stimulus_filter(self, candidates, participant):
        # If the participant answers "Very much", then the next question will be about ponies
        if participant.var.custom_filters and participant.answer == "Very much":
            return [x for x in candidates if x.definition["animal"] == "ponies"]
        else:
            return candidates


trial_maker = AnimalTrialMaker(
    id_="animals",
    trial_class=AnimalTrial,
    nodes=nodes,
    num_trials_per_participant=6,
    max_trials_per_block=2,
    allow_repeated_nodes=True,
    active_balancing_within_participants=True,
    active_balancing_across_participants=True,
    check_performance_at_end=True,
    check_performance_every_trial=True,
    target_n_participants=1,
    target_num_trials_per_node=None,
    recruit_mode="num_participants",
    n_repeat_trials=3,
)

##########################################################################################
# Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    label = "Static experiment demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "custom_filters",
            "Do you want to enable custom stimulus and stimulus version filters?",
            PushButtonControl(["Yes", "No"]),
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.var.set(
                "custom_filters", participant.answer == "Yes"
            )
        ),
        trial_maker,
        SuccessfulEndPage(),
    )
