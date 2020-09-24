import random

from flask import Markup

from .modular_page import (
    AudioPrompt,
    ColourPrompt,
    ImagePrompt,
    ModularPage,
    NAFCControl,
    TextControl,
)
from .page import InfoPage
from .timeline import Module, join
from .trial.non_adaptive import (
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec,
)


class ColorBlindnessTest(Module):
    """
        Color blindness test
    """
    def __init__(
        self,
        label = "color_blind",
        media_url: str = "https://s3.amazonaws.com/ishihara-eye-test/jpg",
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 4,
        hide_after: float = 3.0,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(hide_after),
            self.trial_maker(media_url, time_estimate_per_trial, performance_threshold, hide_after)
        )
        super().__init__(self.label, self.events)


    def instruction_page(self, hide_after):
        if hide_after is None:
            hidden_instructions = ""
        else:
            hidden_instructions = f"This image will disappear after {hide_after} seconds."
        return InfoPage(Markup(
            f"""
            <p>We will now perform a quick test to check your ability to perceive colors.</p>
            <p>
                In each trial, you will be presented with an image that contains a number.
                {hidden_instructions}
                You must enter the number that you see into the text box.
            </p>
            """
        ), time_estimate=10)

    def trial_maker(
            self,
            media_url: str,
            time_estimate_per_trial: float,
            performance_threshold: int,
            hide_after: float
        ):
        class ColorBlindnessTrialMaker(NonAdaptiveTrialMaker):
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

        return ColorBlindnessTrialMaker(
            id_="color_blindness",
            trial_class=self.trial(time_estimate_per_trial, hide_after),
            phase="experiment",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True
        )

    def trial(self, time_estimate: float, hide_after: float):
        class ColorBlindnessTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "color_blindness_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "color_blindness_trial",
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
        return ColorBlindnessTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet("color_blindness", [
            StimulusSpec(
                definition={
                    "label": label,
                    "correct_answer": answer,
                    "url": f"{media_url}/ishihara-{label}.jpg"
                },
                phase="experiment"
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


class ColorVocabularyTest(Module):
    """
        Color vocabulary test
    """
    def __init__(
        self,
        label = "color_vocabulary_test",
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 4,
        colors: list = None
    ):
        self.label = label
        self.colors = self.colors if colors is None else colors
        self.events = join(
            self.instruction_page(),
            self.color_vocabulary_trial_maker(time_estimate_per_trial, performance_threshold, self.colors)
        )
        super().__init__(self.label, self.events)


    colors = [
        ("turquoise", [174, 72,  56]),
        ("magenta",   [300, 100, 50]),
        ("granite",   [0,   0,   40]),
        ("ivory",     [60,  100, 97]),
        ("maroon",    [0,   100, 25]),
        ("navy",      [240, 100, 25])
    ]

    def get_stimulus_set(self, colors: list):
        stimuli = []
        words = [x[0] for x in colors]
        for (correct_answer, hsl) in colors:
            choices = words.copy()
            random.shuffle(choices)
            definition = {
                "target_hsl": hsl,
                "choices": choices,
                "correct_answer": correct_answer
            }
            stimuli.append(StimulusSpec(definition=definition, phase="experiment"))
        return StimulusSet("color_vocabulary", stimuli)

    def color_vocabulary_trial(self, time_estimate: float):
        class ColorVocabularyTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "color_vocabulary_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "color_vocabulary_trial",
                    ColourPrompt(
                        self.definition["target_hsl"],
                        "Which color is shown in the box?",
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
        return ColorVocabularyTrial

    def color_vocabulary_trial_maker(
            self,
            time_estimate_per_trial: float,
            performance_threshold: int,
            colors: list
        ):
        class ColorVocabularyTrialMaker(NonAdaptiveTrialMaker):
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

        return ColorVocabularyTrialMaker(
            id_="color_vocabulary",
            trial_class=self.color_vocabulary_trial(time_estimate_per_trial),
            phase="experiment",
            stimulus_set=self.get_stimulus_set(colors),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True
        )

    def instruction_page(self):
        return InfoPage(Markup(
            """
            <p>We will now perform a quick test to check your ability to name colors.</p>
            <p>
                In each trial, you will be presented with a colored box.
                You must choose which color you see in the box.
            </p>
            """
        ), time_estimate=10)


class HeadphoneCheck(Module):
    """
        Headphone check
    """
    def __init__(
        self,
        label = "headphone_check",
        media_url: str = "https://s3.amazonaws.com/headphone-check",
        time_estimate_per_trial: float = 7.5,
        performance_threshold: int = 4,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(),
            self.headphone_trial_maker(media_url, time_estimate_per_trial, performance_threshold)
        )
        super().__init__(self.label, self.events)


    def get_stimulus_set(self, media_url: str):
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

    def headphone_trial(self, time_estimate: float):
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
            self,
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
            id_="headphone_check_trials",
            trial_class=self.headphone_trial(time_estimate_per_trial),
            phase="experiment",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True
        )

    def instruction_page(self):
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
