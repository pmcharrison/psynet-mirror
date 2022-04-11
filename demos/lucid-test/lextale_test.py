from flask import Markup

from psynet.modular_page import ImagePrompt, ModularPage, NAFCControl
from psynet.page import InfoPage
from psynet.timeline import Module, join
from psynet.trial.static import StaticTrial, StaticTrialMaker, StimulusSet, StimulusSpec

#############
# parameters
#############
num_trials = 12
hide_word_after = 1
time_estimate_trial = 4

score_to_pass = 0
#############
# test
#############


def get_stimulus_set(media_url: str):
    return StimulusSet(
        "lextale_test",
        [
            StimulusSpec(
                definition={
                    "label": label,
                    "correct_answer": correct_answer,
                    "url": f"{media_url}/lextale-{label}.png",
                },
                phase="practice",
            )
            for label, correct_answer in [
                ("1", "yes"),
                ("2", "yes"),
                ("3", "yes"),
                ("4", "yes"),
                ("5", "yes"),
                ("6", "yes"),
                ("7", "yes"),
                ("8", "no"),
                ("9", "no"),
                ("10", "no"),
                ("11", "no"),
                ("12", "no"),
            ]
        ],
    )


def lextale_trial(time_estimate: float, hide_after: float):
    class LextaleTrial(StaticTrial):
        __mapper_args__ = {"polymorphic_identity": "lextale_trial"}
        time_estimate = 3

        def show_trial(self, experiment, participant):
            return ModularPage(
                "lextale_trial",
                ImagePrompt(
                    self.definition["url"],
                    "Does this word exist?",
                    width="100",
                    height="100px",
                    hide_after=hide_after,
                    margin_bottom="15px",
                    text_align="center",
                ),
                NAFCControl(["yes", "no"], ["yes", "no"]),
                time_estimate=self.time_estimate,
            )

    return LextaleTrial


def lextale_trial_maker(
    media_url: str, performance_threshold: int, hide_after: float, num_trials: float
):
    class LextaleTrialMaker(StaticTrialMaker):
        def performance_check(self, experiment, participant, participant_trials):
            """Should return a tuple (score: float, passed: bool)"""
            score = 0
            for trial in participant_trials:
                if trial.answer == trial.definition["correct_answer"]:
                    score += 1
            passed = score >= performance_threshold
            return {"score": score, "passed": passed}

    return LextaleTrialMaker(
        id_="lextale_trial_maker",
        trial_class=lextale_trial(3, hide_after),
        phase="practice",
        stimulus_set=get_stimulus_set(media_url),
        max_trials_per_block=num_trials,
        check_performance_at_end=True,
    )


def instruction_page(hide_after):
    return InfoPage(
        Markup(
            f"""
        <h3>Lexical decision task</h3>
        <p>Here, you will be presented in each trial with either an existing word in English or a fake word that does not exist.</p>
        <p>
            <b>Your task is to decide whether or not the word exists.</b>
            <br><br>Each word will disappear in {hide_after} second and you will see a total of {num_trials} words.
        </p>
        """
        ),
        time_estimate=65,
    )


def lextale_test(
    media_url: str = "https://s3.amazonaws.com/lextale-test-materials",
    performance_threshold: int = score_to_pass,
    hide_after: float = hide_word_after,
    num_trials: float = num_trials,
):
    return Module(
        "lextale_test",
        join(
            instruction_page(hide_after),
            lextale_trial_maker(
                media_url, performance_threshold, hide_after, num_trials
            ),
        ),
    )
