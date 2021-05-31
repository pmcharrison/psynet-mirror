import json

from flask import Markup, escape

import psynet.experiment
from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.static import StaticTrial, StaticTrialMaker, stimulus_set_from_dir
from psynet.utils import get_logger

logger = get_logger()

version = "v1"

practice_stimuli = stimulus_set_from_dir(
    id_="practice_stimuli",
    input_dir="input/practice",
    media_ext=".wav",
    phase="practice",
    version=version,
    s3_bucket="audio-stimulus-set-from-dir-demo",
)
experiment_stimuli = stimulus_set_from_dir(
    id_="experiment_stimuli",
    input_dir="input/experiment",
    media_ext=".wav",
    phase="experiment",
    version=version,
    s3_bucket="audio-stimulus-set-from-dir-demo",
)

# Run ``psynet prepare`` (or ``psynet prepare --force``) to prepare the stimulus sets.
# Note: you can .gitignore the input/ directory, where you store your
# stimuli. However, don't .gitignore the automatically generated
# _stimulus_sets directory - this needs to be accessible by Heroku.


class CustomTrial(StaticTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        dump = escape(json.dumps(self.summarize(), indent=4))
        text = Markup(
            f"""
            <p>
                Here is a JSON summary of the trial:
            </p>
            <pre>{dump}</pre>
            """
        )

        return ModularPage(
            "question_page",
            AudioPrompt(self.media_url, text),
            PushButtonControl(["Yes", "No"]),
            time_estimate=5,
        )


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        InfoPage("We begin with the practice trials.", time_estimate=5),
        StaticTrialMaker(
            id_="audio_practice",
            trial_class=CustomTrial,
            phase="practice",
            stimulus_set=practice_stimuli,
            time_estimate_per_trial=5,
            target_num_participants=3,
            recruit_mode="num_participants",
        ),
        InfoPage("We continue with the experiment trials.", time_estimate=5),
        StaticTrialMaker(
            id_="audio_experiment",
            trial_class=CustomTrial,
            phase="experiment",
            stimulus_set=experiment_stimuli,
            time_estimate_per_trial=5,
            target_num_participants=10,
            recruit_mode="num_participants",
        ),
        SuccessfulEndPage(),
    )
