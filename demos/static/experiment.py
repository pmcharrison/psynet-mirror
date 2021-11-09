# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline
from psynet.trial.static import (
    StaticTrial,
    StaticTrialMaker,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


##########################################################################################
# Stimuli
##########################################################################################

stimulus_set = StimulusSet(
    "animals",
    [
        StimulusSpec(
            definition={"animal": animal},
            version_specs=[
                StimulusVersionSpec(definition={"text_color": text_color})
                for text_color in ["red", "green", "blue"]
            ],
            phase="experiment",
            block=block,
        )
        for animal in ["cats", "dogs", "fish", "ponies"]
        for block in ["A", "B", "C"]
    ],
)


class AnimalTrial(StaticTrial):
    __mapper_args__ = {"polymorphic_identity": "animal_trial"}

    time_estimate = 3

    def show_trial(self, experiment, participant):
        text_color = self.definition["text_color"]
        animal = self.definition["animal"]
        block = self.block

        header = f"<h4 id='trial-position'>Trial {self.position + 1}</h3>"

        if self.is_repeat_trial:
            header = (
                header
                + f"<h4>Repeat trial {self.repeat_trial_index + 1} out of {self.num_repeat_trials}</h3>"
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
            PushButtonControl(["Not at all", "A little", "Very much"]),
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
        """Should return a tuple (score: float, passed: bool)"""
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

    def custom_stimulus_version_filter(self, candidates, participant):
        # If the participant has answered at least three trials, make the text color red.
        trials = self.get_participant_trials(participant)
        complete_trials = [t for t in trials if t.complete]
        if participant.var.custom_filters and len(complete_trials) >= 3:
            return [x for x in candidates if x.definition["text_color"] == "red"]
        return candidates


trial_maker = AnimalTrialMaker(
    id_="animals",
    trial_class=AnimalTrial,
    phase="experiment",
    stimulus_set=stimulus_set,
    max_trials_per_block=2,
    allow_repeated_stimuli=True,
    max_unique_stimuli_per_block=None,
    active_balancing_within_participants=True,
    active_balancing_across_participants=True,
    check_performance_at_end=True,
    check_performance_every_trial=True,
    target_num_participants=1,
    target_num_trials_per_stimulus=None,
    recruit_mode="num_participants",
    num_repeat_trials=3,
)

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

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
