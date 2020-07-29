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
    NAFCControl
)

def get_stimulus_set(media_url: str):
    return StimulusSet("headphone_check", [
        StimulusSpec(
            definition={
                "label": label,
                "correct_answer": answer,
                "url": f"{media_url}/antiphase_HC_{label}.wav"
            },
            phase="experiment"
        )
        for label, answer in
        [
            ("ISO", "2"),
            ("IOS", "3"),
            ("SOI", "1"),
            ("SIO", "1"),
            ("OSI", "2"),
            ("OIS", "3")
        ]
    ])

def headphone_trial(time_estimate: float):
    class HeadphoneTrial(NonAdaptiveTrial):
        __mapper_args__ = {"polymorphic_identity": "headphone_trial"}

        def show_trial(self, experiment, participant):
            return ModularPage(
                "headphone_trial",
                AudioPrompt(
                    self.definition["url"],
                    "Which sound was softest (quietest) -- 1, 2, or 3?"
                ),
                NAFCControl(
                    ["1", "2", "3"]
                ),
                time_estimate=time_estimate
            )
    return HeadphoneTrial

def headphone_trial_maker(
        media_url: str,
        time_estimate_per_trial: float,
        performance_threshold: int
    ):
    class HeadphoneTrialMaker(NonAdaptiveTrialMaker):
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

    return HeadphoneTrialMaker(
        id_="headphone_check",
        trial_class=headphone_trial(time_estimate_per_trial),
        phase="experiment",
        stimulus_set=get_stimulus_set(media_url),
        time_estimate_per_trial=time_estimate_per_trial,
        check_performance_at_end=True
    )

def instruction_page():
    return InfoPage(Markup(
        """
        <p>We will now perform a quick test to check that you are wearing headphones.</p>
        <p>
            In each trial, you will hear three sounds separated by silences.
            Your task will be to judge
            <strong>which sound was softest (quietest).</strong>
        </p>
        """
    ), time_estimate=10)

def headphone_check(
        media_url: str = "https://s3.amazonaws.com/headphone-check",
        time_estimate_per_trial: float = 7.5,
        performance_threshold: int = 4
    ):
    return Module(
        "headphone_check",
        join(
            instruction_page(),
            headphone_trial_maker(media_url, time_estimate_per_trial, performance_threshold)
        )
    )
