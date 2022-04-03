from markupsafe import Markup

from psynet.modular_page import ImagePrompt, ModularPage, NAFCControl
from psynet.page import InfoPage
from psynet.timeline import Module, join
from psynet.trial.non_adaptive import (
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec,
)


class LexTaleTest(Module):
    """
    This is an adapted version (shorter) of the  original LexTale test, which checks participants' English proficiency
    in a lexical decision task: "Lemhöfer, K., & Broersma, M. (2012). Introducing LexTALE: A quick and valid lexical test
    for advanced learners of English. Behavior research methods, 44(2), 325-343". In each trial, a word is presented
    for a short period of time (determined by ``hide_after``) and the participant must decide whether the word is an existing word in English or
    it does not exist. The words are chosen from the original study, which used and validated highly unfrequent
    words in English to make the task very difficult for non-native English speakers. See the documentation for further details.
    Parameters
    ----------
    label : string, optional
        The label for the LexTale test, default: "lextale_test".
    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 2.0.
    performance_threshold : int, optional
        The performance threshold, default: 10.
    hide_after : float, optional
        The time in seconds after the word disappears, default: 1.0.
    num_trials : float, optional
        The total number of trials to display, default: 12.
    """

    def __init__(
        self,
        label="lextale_test",
        time_estimate_per_trial: float = 2.0,
        performance_threshold: int = 10,
        media_url: str = "https://s3.amazonaws.com/lextale-test-materials",
        hide_after: float = 1,
        num_trials: float = 12,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(hide_after, num_trials),
            self.trial_maker(
                media_url,
                time_estimate_per_trial,
                performance_threshold,
                hide_after,
                num_trials,
            ),
        )
        super().__init__(self.label, self.events)

    def instruction_page(self, hide_after, num_trials):
        return InfoPage(
            Markup(
                f"""
            <h3>Lexical decision task</h3>
            <p>In each trial, you will be presented with either an exisitng word in English or a fake word that does not exist.</p>
           <p>
                <b>Your task is to decide whether the word exists not.</b>
                <br><br>Each word will disappear in {hide_after} seconds and you will see a total of {num_trials} words.
            </p>
            """
            ),
            time_estimate=5,
        )

    def trial_maker(
        self,
        media_url: str,
        time_estimate_per_trial: float,
        performance_threshold: int,
        hide_after: float,
        num_trials: float,
    ):
        class LextaleTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score += 1
                passed = score >= performance_threshold
                return {"score": score, "passed": passed}

        return LextaleTrialMaker(
            id_="lextale",
            trial_class=self.trial(time_estimate_per_trial, hide_after),
            phase="screening",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            max_trials_per_block=num_trials,
            check_performance_at_end=True,
        )

    def trial(self, time_estimate: float, hide_after: float):
        class LextaleTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "lextale_trial"}

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
                    time_estimate=time_estimate,
                )

        return LextaleTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet(
            "lextale",
            [
                StimulusSpec(
                    definition={
                        "label": label,
                        "correct_answer": correct_answer,
                        "url": f"{media_url}/lextale-{label}.png",
                    },
                    phase="screening",
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
