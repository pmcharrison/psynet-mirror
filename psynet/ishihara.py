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
    ImagePrompt,
    TextControl
)

def get_stimulus_set(media_url: str):
    return StimulusSet([
        StimulusSpec(
            definition={
                "label": label,
                "correct_answer": answer,
                "url": f"{media_url}/ishihara-{label}.jpg"
            },
            phase="test"
        )
        for label, answer in
        [
            ("1", "12"),
            ("2", "8"),
            ("3", "29"),
            ("4", "5"),
            ("5", "3"),
            ("6", "15")
        ]
    ])

def ishihara_trial(time_estimate: float, hide_after: float):
    class IshiharaTrial(NonAdaptiveTrial):
        __mapper_args__ = {"polymorphic_identity": "ishihara_trial"}

        def show_trial(self, experiment, participant):
            return ModularPage(
                "ishihara_trial",
                ImagePrompt(
                    self.definition["url"],
                    "Write down the number in the image.",
                    width="410px",
                    height="403px",
                    hide_after=hide_after,
                    margin_bottom="15px",
                    text_align="center"
                ),
                TextControl(width="100px"),
                time_estimate=time_estimate
            )
    return IshiharaTrial

def ishihara_trial_maker(
        media_url: str,
        time_estimate_per_trial: float,
        performance_threshold: int,
        hide_after: float
    ):
    class IshiharaTrialMaker(NonAdaptiveTrialMaker):
        def performance_check(self, experiment, participant, participant_trials):
            """Should return a tuple (score: float, passed: bool)"""
            score = 0
            for trial in participant_trials:
                if trial.answer == trial.definition["correct_answer"]:
                    score +=1
            passed = score >= performance_threshold
            return {
                "score": score,
                "passed": passed
            }

    return IshiharaTrialMaker(
        trial_class=ishihara_trial(time_estimate_per_trial, hide_after),
        phase="test",
        stimulus_set=get_stimulus_set(media_url),
        time_estimate_per_trial=time_estimate_per_trial,
        new_participant_group=True,
        check_performance_at_end=True
    )

def instruction_page(hide_after):
    if hide_after is None:
        hidden_instructions = ""
    else:
        hidden_instructions = f"This image will disappear after {hide_after} seconds."
    return InfoPage(Markup(
        f"""
        <p>We will now perform a quick test to check your ability to perceive colours.</p>
        <p>
            In each trial, you will be presented with an image that contains a number.
            {hidden_instructions}
            You must enter the number that you see into the text box.
        </p>
        """
    ), time_estimate=10)

def colour_blind_test(
        media_url: str = "https://s3.amazonaws.com/ishihara-eye-test/jpg",
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 4,
        hide_after: float = 3.0
    ):
    return Module(
        "headphone_check",
        join(
            instruction_page(hide_after),
            ishihara_trial_maker(media_url, time_estimate_per_trial, performance_threshold, hide_after)
        )
    )
