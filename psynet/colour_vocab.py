import random

from flask import Markup

from .timeline import Module, join

from .trial.non_adaptive import (
    NonAdaptiveNetwork,
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec
)

from .page import InfoPage

from .modular_page import(
    ModularPage,
    AudioPrompt,
    ColourPrompt,
    NAFCControl
)

DEFAULT_COLOURS = [
    ("turquoise", [174, 72,  56]),
    ("magenta",   [300, 100, 50]),
    ("granite",   [0,   0,   40]),
    ("ivory",     [60,  100, 97]),
    ("maroon",    [0,   100, 25]),
    ("navy",      [240, 100, 25])
]

def get_stimulus_set(colours: list):
    stimuli = []
    words = [x[0] for x in colours]
    for i, (correct_answer, hsl) in enumerate(colours):
        choices = words.copy()
        random.shuffle(choices)
        definition = {
            "target_hsl": hsl,
            "choices": choices,
            "correct_answer": correct_answer
        }
        stimuli.append(StimulusSpec(definition=definition, phase="experiment"))
    return StimulusSet(stimuli)

def colour_vocab_trial(time_estimate: float):
    class ColourVocabTrial(NonAdaptiveTrial):
        __mapper_args__ = {"polymorphic_identity": "colour_vocab_trial"}

        def show_trial(self, experiment, participant):
            return ModularPage(
                "colour_vocab_trial",
                ColourPrompt(
                    self.definition["target_hsl"],
                    "Which colour is shown in the box?",
                    text_align="center"
                ),
                NAFCControl(
                    self.definition["choices"],
                    arrange_vertically=False,
                    min_width="150px",
                    margin="10px"
                ),
                time_estimate=time_estimate
            )
    return ColourVocabTrial

def colour_vocab_trial_maker(
        time_estimate_per_trial: float,
        performance_threshold: int,
        colours: list
    ):
    class ColourVocabTrialMaker(NonAdaptiveTrialMaker):
        def performance_check(self, experiment, participant, participant_trials):
            """Should return a tuple (score: float, passed: bool)"""
            score = 0
            for trial in participant_trials:
                if trial.answer == trial.definition["correct_answer"]:
                    score += 1
            passed = score >= performance_threshold
            return {
                "score": score,
                "passed": passed
            }

    return ColourVocabTrialMaker(
        trial_class=colour_vocab_trial(time_estimate_per_trial),
        phase="experiment",
        stimulus_set=get_stimulus_set(colours),
        time_estimate_per_trial=time_estimate_per_trial,
        new_participant_group=True,
        check_performance_at_end=True
    )

def instruction_page():
    return InfoPage(Markup(
        f"""
        <p>We will now perform a quick test to check your ability to name colours.</p>
        <p>
            In each trial, you will be presented with a coloured box.
            You must choose which colour you see in the box.
        </p>
        """
    ), time_estimate=10)

def colour_vocab_test(
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 4,
        colours: list = DEFAULT_COLOURS
    ):
    return Module(
        "colour_vocab_test",
        join(
            instruction_page(),
            colour_vocab_trial_maker(time_estimate_per_trial, performance_threshold, colours)
        )
    )
