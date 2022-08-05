import psynet.experiment
from psynet.asset import DebugStorage
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.static import StaticTrial, StaticTrialMaker, StimulusSetFromDir
from psynet.utils import get_logger

logger = get_logger()


class CustomTrial(StaticTrial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage(
            "question_page",
            AudioPrompt(self.assets["prompt"], "Do you like this audio file?"),
            PushButtonControl(["Yes", "No"]),
            time_estimate=self.time_estimate,
        )


class Exp(psynet.experiment.Experiment):
    label = "Audio stimulus set from directory demo"
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        InfoPage("We begin with the practice trials.", time_estimate=5),
        StaticTrialMaker(
            id_="audio_practice",
            trial_class=CustomTrial,
            phase="practice",
            stimuli=StimulusSetFromDir(
                id_="practice", input_dir="input/practice", media_ext=".wav"
            ),
            target_num_participants=0,
            recruit_mode="num_participants",
        ),
        InfoPage("We continue with the experiment trials.", time_estimate=5),
        StaticTrialMaker(
            id_="audio_experiment",
            trial_class=CustomTrial,
            phase="experiment",
            stimuli=StimulusSetFromDir(
                id_="experiment", input_dir="input/experiment", media_ext=".wav"
            ),
            target_num_participants=10,
            recruit_mode="num_participants",
        ),
        SuccessfulEndPage(),
    )
