from statistics import mean
from flask import Markup

import numpy as np

import psynet.experiment
from psynet.timeline import (
    Timeline,
)
from psynet.page import (
    SuccessfulEndPage,
    VolumeCalibration,
    InfoPage
)
from psynet.modular_page import(
    ModularPage,
    AudioPrompt,
    AudioRecordControl,
    NAFCControl,
    AudioMeterControl
)
from psynet.trial.audio import (
    AudioImitationChainTrial,
    AudioImitationChainNode,
    AudioImitationChainSource,
    AudioImitationChainTrialMaker,
    AudioImitationChainNetwork
)

from psynet.utils import get_logger
logger = get_logger()

import rpdb

import psynet.media
psynet.media.LOCAL_S3 = True # set this to False if you want to actually use S3 instead of a local version

NOTE_DURATION = 0.25
NOTE_IOI = 1.0
SING_DURATION = 4.0
MAX_MEAN_ABSOLUTE_DEVIATION = 5.0
SAMPLE_RATE = 44100

def as_native_type(x):
    if type(x).__module__ == np.__name__:
        return x.item()
    return x

class CustomTrial(AudioImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        return ModularPage(
            "singing_page",
            AudioPrompt(self.origin.target_url, "Please sing back the melody to the syllable 'Ta'."),
            AudioRecordControl(
                duration=SING_DURATION,
                s3_bucket="iterated-singing-demo",
                public_read=False
            ),
            time_estimate=5
        )

    def analyse_recording(self, audio_file: str, output_plot: str):
        import singing_extract
        raw = singing_extract.analyze(
            audio_file,
            plot_options=singing_extract.PlotOptions(
                save=True,
                path=output_plot,
                format="png"
            )
        )
        raw = [{key: as_native_type(value) for key, value in x.items()} for x in raw] # move to native Python types
        midi = [x["median_f0"] for x in raw]
        error = get_singing_error(midi, self.definition)
        failed = (
            (not error["correct_num_notes"])
            or
            (error["mean_absolute_deviation"] > MAX_MEAN_ABSOLUTE_DEVIATION)
        )
        return {
            "failed": failed,
            "error": error,
            "midi": midi,
            "raw": raw,
            "no_plot_generated": False
        }

def diff(x):
    return [j - i for i, j in zip(x[: -1], x[1 :])]

def get_singing_error(sung_midi, target_midi):
    assert len(target_midi) > 1

    target_int = diff(target_midi)
    actual_int = diff(sung_midi)

    if len(target_int) != len(actual_int):
        return {
            "correct_num_notes": False,
            "mean_absolute_deviation": None
        }
    else:
        absolute_deviations = [abs(j - i) for i, j in zip(target_int, actual_int)]
        return {
            "correct_num_notes": True,
            "mean_absolute_deviation": mean(absolute_deviations)
        }

class CustomNetwork(AudioImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    s3_bucket = "iterated-singing-demo"

class CustomNode(AudioImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarise_trials(self, trials: list, experiment, participant):
        melodies = [trial.analysis["midi"] for trial in trials]
        return [mean(x) for x in zip(*melodies)]

    def synthesise_target(self, output_file):
        import singing_extract
        midis = self.definition
        durations = [NOTE_DURATION for _ in midis]
        onsets = [i * NOTE_IOI for i in range(len(midis))]
        singing_extract.generate_sine_tones(midis, durations, onsets, SAMPLE_RATE, output_file)

class CustomSource(AudioImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return [55, 59, 62]


##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        # VolumeCalibration(),
        # ModularPage(
        #     "record_calibrate",
        #     """
        #     Please speak into your microphone and check that the sound is registered
        #     properly. If the sound is too quiet, try moving your microphone
        #     closer or increasing the input volume on your computer.
        #     """,
        #     AudioMeterControl(),
        #     time_estimate=5
        # ),
        # InfoPage(
        #     Markup("""
        #     <p>
        #         In this experiment you will hear some melodies. Your task will be to sing
        #         them back as accurately as possible.
        #     </p>
        #     <p>
        #         For the recording to work effectively, we need you to sing in a specific way.
        #         In particular, we want you to sing each note with a short and sharp
        #         'Ta' sound, so a melody sounds like 'Ta! Ta! Ta!'.
        #     </p>
        #     """),
        #     time_estimate=5
        # ),
        AudioImitationChainTrialMaker(
            id_="iterated_singing_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            time_estimate_per_trial=5,
            chain_type="across",
            num_iterations_per_chain=10,
            num_trials_per_participant=5,
            num_chains_per_participant=None,
            num_chains_per_experiment=5,
            trials_per_node=1,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="num_trials",
            target_num_participants=None
        ),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
