from statistics import mean

import singing_extract.singing_extract.singing_extract as sing
from flask import Markup
from melody import params, utils
from melody.resources import GenderSplit, SingingCalibration, ToneJSVolumeTest

import psynet.experiment
import psynet.media
from psynet.asset import DebugStorage

# from psynet.asset import S3Storage
from psynet.consent import AudiovisualConsent, MainConsent
from psynet.js_synth import JSSynth, Note
from psynet.modular_page import AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline, join
from psynet.trial.audio import (
    AudioImitationChainNetwork,
    AudioImitationChainNode,
    AudioImitationChainTrial,
    AudioImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()

assert False, "This demo needs the melody package to be updated for the latest PsyNet"

# global parameters
INITIAL_RECRUITMENT_SIZE = 1
TIME_ESTIMATE_TRIAL = params.singing_2intervals["sing_duration"] * 2
DESIGN_PARAMS = {
    "num_trials_per_participant": 10,
    "max_trials_per_participant": 15,
    "num_trials_practice": 3,
    "num_nodes_per_chain": 5,
    "chain_type": "within",
    "num_chains_per_participant": 2,
    "num_chains_per_exp": None,
    "recruit_mode": "num_participants",
    "target_num_participants": 25,
}


# experiment parts
class IteratedSingingTrial(AudioImitationChainTrial):
    time_estimate = None

    def make_definition(self, experiment, participant):
        definition = super().make_definition(experiment, participant)

        logger.info(
            "********** Gender of participant: {0} **********".format(
                participant.var.gender
            )
        )
        reference_pitch = utils.sample_reference_pitch(
            params.roving_mean[
                participant.var.gender
            ],  # roving_mean selected based on participant's gender
            params.roving_width["default"],
        )
        definition["reference_pitch"] = reference_pitch
        definition[
            "target_pitches"
        ] = utils.convert_interval_sequence_to_absolute_pitches(
            intervals=definition["intervals"],
            reference_pitch=reference_pitch,
            reference_mode=params.singing_2intervals["reference_mode"],
        )

        return definition

    def show_trial(self, experiment, participant):
        return ModularPage(
            "singing_page",
            JSSynth(
                Markup(
                    f"""
                    <h3>Imitate the melody</h3>
                    Listen to the melody and sing it back to the syllable 'Ta'.
                    <br><br>
                    {self.progress_message}
                    """
                ),
                sequence=[Note(x) for x in self.definition["target_pitches"]],
                timbre=params.timbre,
                default_duration=params.note_duration,
                default_silence=params.note_silence,
            ),
            AudioRecordControl(
                duration=params.singing_2intervals["sing_duration"],
                show_meter=False,
                controls=False,
                auto_advance=False,
            ),
            time_estimate=self.time_estimate,
            events={
                "promptStart": Event(is_triggered_by="trialStart", delay=0.25),
                "recordStart": Event(is_triggered_by="promptEnd", delay=0.5),
            },
            progress_display=ProgressDisplay(
                # show_bar=False,
                stages=[
                    ProgressStage(3, "Listen to the melody and wait...", "orange"),
                    ProgressStage(3, "START SINGING!", "red"),
                    ProgressStage(0.5, "Finished recording.", "green"),
                    ProgressStage(
                        0.5,
                        "Uploading... please wait and click next",
                        "orange",
                        persistent=True,
                    ),
                ],
            ),
        )

    @property
    def progress_message(self):
        raise NotImplementedError

    def analyze_recording(self, audio_file: str, output_plot: str):
        raw = sing.analyze(
            audio_file,
            params.singing_2intervals,
            target_pitches=self.definition["target_pitches"],
            plot_options=sing.PlotOptions(save=True, path=output_plot, format="png"),
        )
        raw = [
            {key: utils.as_native_type(value) for key, value in x.items()} for x in raw
        ]
        sung_pitches = [x["median_f0"] for x in raw]
        sung_intervals = utils.convert_absolute_pitches_to_interval_sequence(
            sung_pitches, params.singing_2intervals["reference_mode"]
        )
        target_intervals = utils.convert_absolute_pitches_to_interval_sequence(
            self.definition["target_pitches"],
            params.singing_2intervals["reference_mode"],
        )
        stats = sing.compute_stats(
            sung_pitches,
            self.definition["target_pitches"],
            sung_intervals,
            target_intervals,
        )
        is_failed = utils.failing_criteria(
            sung_intervals,
            params.singing_2intervals["num_int"],
            sung_pitches,
            self.definition["target_pitches"],
            params.singing_2intervals["max_mean_interval_error"],
            params.singing_2intervals["max_interval_size"],
            params.singing_2intervals["max_melody_pitch_range"],
            params.singing_2intervals["reference_mode"],
        )
        return {
            "failed": is_failed["failed"],
            "reason": is_failed["reason"],
            "error": is_failed["output_singing_error"],
            "target_pitches": self.definition["target_pitches"],
            "target_intervals": target_intervals,
            "sung_pitches": sung_pitches,
            "sung_intervals": sung_intervals,
            "raw": raw,
            "no_plot_generated": False,
            "stats": stats,
        }


class CustomTrialPractice(IteratedSingingTrial):
    wait_for_feedback = True

    def gives_feedback(self, experiment, participant):
        return True

    time_estimate = 10

    @property
    def progress_message(self):
        trial_number = self.position + 1

        return Markup(
            f"""
            <i>Trial number {trial_number} out of {DESIGN_PARAMS["num_trials_practice"]} trials.</i>
            """
        )

    def show_feedback(self, experiment, participant):
        feedback = utils.feedback_generator(self.details["analysis"])
        if feedback["status"] == "perfect":
            return InfoPage(
                Markup(
                    f"""
                    <h3>Feedback</h3>
                    <hr>
                    {feedback["message"]}
                    <br><br>
                    Keep singing like this throughout the experiment and you will get the full bonus.
                    <hr>
                    <img style="width:50%" src="/static/images/happy.png"  alt="happy">
                    """
                ),
                time_estimate=5,
            )
        elif feedback["status"] == "ok":
            return InfoPage(
                Markup(
                    f"""
                    <h3>Feedback</h3>
                    <hr>
                    {feedback["message"]}
                    <br><br>
                    Please try to improve your performance by
                    singing each note in the melody as accurately as possible.
                    <hr>
                    <img style="width:50%" src="/static/images/neutral.png"  alt="happy">
                    """
                ),
                time_estimate=5,
            )

        else:
            return InfoPage(
                Markup(
                    f"""
                    <h3>Feedback</h3>
                    <hr>
                    {feedback["message"]}
                    <br><br>
                    <b><b>Note:</b></b> Make sure that you sing long notes (about 1 second long) and to leave
                    a silent gap between notes.
                    <br><br>
                    <b><b>If you don't improve your performance, the experiment will terminate.</b></b>
                    <hr>
                    <img style="width:50%" src="/static/images/sad.png"  alt="sad">
                    """
                ),
                time_estimate=5,
            )


class IteratedSingingTrialExperiment(IteratedSingingTrial):
    time_estimate = TIME_ESTIMATE_TRIAL

    @property
    def progress_message(self):
        trial_number = self.position + 1

        return Markup(
            f"""
            <i>Trial number {trial_number} out of {DESIGN_PARAMS["num_trials_per_participant"]} required trials.
            The maximum number of possible trials is {DESIGN_PARAMS["max_trials_per_participant"]}.</i>
            """
        )


class CustomNode(AudioImitationChainNode):
    def summarize_trials(self, trials: list, experiment, participant):
        sung_intervals = [trial.analysis["sung_intervals"] for trial in trials]
        return dict(intervals=[mean(x) for x in zip(*sung_intervals)])


class CustomNodePractice(CustomNode):
    def create_initial_seed(self, experiment, participant):
        intervals = utils.sample_interval_sequence(
            n_int=params.singing_2intervals["num_int"],
            max_interval_size=3,
            max_melody_pitch_range=params.singing_2intervals["max_melody_pitch_range"],
            discrete=params.singing_2intervals["discrete"],
            reference_mode=params.singing_2intervals["reference_mode"],
        )
        return dict(intervals=intervals)


class CustomNodeExperiment(CustomNode):
    def create_initial_seed(self, experiment, participant):
        intervals = utils.sample_interval_sequence(
            n_int=params.singing_2intervals["num_int"],
            max_interval_size=params.singing_2intervals["max_interval_size"],
            max_melody_pitch_range=params.singing_2intervals["max_melody_pitch_range"],
            discrete=params.singing_2intervals["discrete"],
            reference_mode=params.singing_2intervals["reference_mode"],
        )
        return dict(intervals=intervals)


Welcome = InfoPage(
    Markup(
        """
        <h3>Welcome</h3>
        <hr>
        In this experiment, you will hear melodies and be asked to sing them back.
        <br><br>
        <hr>
        """
    ),
    time_estimate=3,
)


class SingingImitationTrialMakerPractice(AudioImitationChainTrialMaker):
    performance_check_type = "performance"
    performance_check_threshold = 0
    give_end_feedback_passed = False


SingingFeedback = join(
    InfoPage(
        Markup(
            """
            <h3>Practice</h3>
            <hr>
            You will now get familiar with the singing task. In each trial,
            you will hear a melody and your goal is to sing
            the melody back to the syllable 'Ta'.
            <br><br>
            We will analyse your performance and give you feedback after each trial.<b><b> The final bonus
            will depend on your performance</b></b>
            <hr>
            Click <b>next</b> to start the practice.
            """
        ),
        time_estimate=5,
    ),
    SingingImitationTrialMakerPractice(
        id_="singing_iterated_practice",
        trial_class=CustomTrialPractice,
        node_class=CustomNodePractice,
        chain_type="within",
        num_nodes_per_chain=1,
        num_trials_per_participant=DESIGN_PARAMS["num_trials_practice"],
        num_chains_per_participant=DESIGN_PARAMS["num_trials_practice"],
        num_chains_per_experiment=None,
        trials_per_node=1,
        balance_across_chains=True,
        check_performance_at_end=False,
        check_performance_every_trial=False,
        recruit_mode="num_participants",
        target_num_participants=0,
        wait_for_networks=True,
    ),
)


SingingMainTask1 = join(
    InfoPage(
        Markup(
            """
            Congratulations, we now move on to the actual task.
            """
        ),
        time_estimate=3,
    ),
    InfoPage(
        Markup(
            f"""
            <h3>Main singing task</h3>
            <hr>
            You will take {DESIGN_PARAMS["num_trials_per_participant"]} singing trials. If you fail, we will repeat
            the trials up to a maximum of {DESIGN_PARAMS["max_trials_per_participant"]} trials.
            <br><br>
            <b><b>Attention:</b></b>
            <ol><li>Your performance will be analyzed after each trial.</li>
            <li>The final bonus will depend on your performance in each trial.</li>
            <li>To get the full bonus, sing as accurately as possible throughout the experiment.</li>
            </ol>
            <hr>
            Click <b>next</b> to start singing!
            """
        ),
        time_estimate=5,
    ),
    AudioImitationChainTrialMaker(
        id_="first_trial_maker",
        trial_class=IteratedSingingTrialExperiment,
        node_class=CustomNodeExperiment,
        phase="experiment",
        chain_type=DESIGN_PARAMS["chain_type"],
        num_trials_per_participant=DESIGN_PARAMS["max_trials_per_participant"],
        num_nodes_per_chain=DESIGN_PARAMS["num_nodes_per_chain"],
        num_chains_per_participant=DESIGN_PARAMS[
            "num_chains_per_participant"
        ],  # set to None if chain_type="across"
        num_chains_per_experiment=DESIGN_PARAMS[
            "num_chains_per_exp"
        ],  # set to None if chain_type="within"
        trials_per_node=1,
        balance_across_chains=False,
        check_performance_at_end=False,
        check_performance_every_trial=False,
        propagate_failure=False,
        recruit_mode=DESIGN_PARAMS["recruit_mode"],
        target_num_participants=DESIGN_PARAMS["target_num_participants"],
    ),
)


class Exp(psynet.experiment.Experiment):
    label = "Iterated singing demo"
    initial_recruitment_size = INITIAL_RECRUITMENT_SIZE

    # assets = AssetRegistry(asset_storage=S3Storage())
    asset_storage = DebugStorage()

    timeline = Timeline(
        MainConsent(),
        AudiovisualConsent(),
        Welcome,
        GenderSplit,
        ToneJSVolumeTest,
        SingingCalibration,
        SingingFeedback,
        SingingMainTask1,
        SuccessfulEndPage(),
    )

    def test_experiment(self):
        pass
