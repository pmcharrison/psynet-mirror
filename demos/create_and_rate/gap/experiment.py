# pylint: disable=unused-import,abstract-method,unused-argument
##########################################################################################
# Imports
##########################################################################################
from flask import Markup

import psynet.experiment
from psynet.asset import DebugStorage
from psynet.consent import NoConsent
from psynet.modular_page import (
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
    PushButtonControl,
)
from psynet.page import SuccessfulEndPage
from psynet.timeline import (
    Event,
    MediaSpec,
    ProgressDisplay,
    ProgressStage,
    Timeline,
    join,
)
from psynet.trial.audio import AudioImitationChainNode, AudioImitationChainTrial
from psynet.trial.create_and_rate import (
    CreateAndRateNodeMixin,
    CreateAndRateTrialMakerMixin,
    CreateTrialMixin,
    SelectTrialMixin,
)
from psynet.trial.imitation_chain import ImitationChainTrial, ImitationChainTrialMaker
from psynet.utils import get_logger

from .utils import get_instructions, setup_experiment

logger = get_logger()

N_CREATORS = 2
N_RATERS = 7
MAX_RECORDING_DURATION = 5

S3_BUCKET = "serial-prosody"

STIMULUS_DIR = "stimuli/initial_seed"
STIMULI_FILE = STIMULUS_DIR + "/stimuli.txt"

with open(STIMULI_FILE) as f:
    STIMULUS_LINES = [line.replace("\n", "") for line in f.readlines()]
name_stimuli = [line.split("|")[3] for line in STIMULUS_LINES]

NUMBER_OF_SENTENCES = 10

REPETITIONS_PER_SENTENCE = 5

NUM_TRIALS_PER_PARTICIPANT = 40

NUM_ITERATIONS_PER_CHAIN = 20


class CreateTrial(CreateTrialMixin, AudioImitationChainTrial):
    time_estimate = 13
    accumulate_answers = True

    def analyze_recording(self, audio_file: str, output_plot: str):
        # TODO to be implemented
        # if is_create_trial_from_answer(self.answer):
        #     # Normalize audio
        #     normalize_volume(audio_file, audio_file)
        #     logger.info("Normalize recording: {}".format(audio_file))
        #
        #     logger.info("Analyze recording: {}".format(self.answer))
        #     answer = self.answer[2]
        #
        #     if answer == "My own recording is bad":
        #         # Fail current recording
        #         return {
        #             'failed': True,
        #             'reason': "My own recording is bad"
        #         }
        #     else:
        #         return {
        #             'failed': False,
        #             'reason': "My own recording is correct"
        #         }
        # else:
        #     return {
        #         'failed': False,
        #         'reason': 'Stimuli were only rated, not created'
        #     }
        pass

    def get_listen_page(self):
        return ModularPage(
            "serial-prosody-listen",
            prompt=AudioPrompt(
                url=self.definition["url"],
                text=Markup(
                    """
                        Listen to the recording. Feel free to listen to the recording again by clicking on the button "Play".
                        Press "Next" when you are ready. The recording procedure will start automatically. <br><br>
                        <button type="button" id="play-button" class="btn btn-success btn-lg float-right" onclick="psynet.audio.prompt.stop(); psynet.audio.prompt.play();">Play</button>
                        """
                ),
            ),
            events={
                "hideNextButton": Event(
                    is_triggered_by="trialStart",
                    js="document.getElementById('next-button').hidden = true",
                ),
                "showNextButton": Event(
                    is_triggered_by="trialStart",
                    js="document.getElementById('next-button').hidden = false",
                    delay=MAX_RECORDING_DURATION,
                ),
            },
            time_estimate=MAX_RECORDING_DURATION,
        )

    def get_recording_progress_display(self):
        colors = ["orange", "red", "blue", "green"]
        durations = [MAX_RECORDING_DURATION] * 3 + [0.2]
        messages = [
            "Listen and think of a situation",
            "Record as if you are in the situation",
            "Playback",
            "Done!",
        ]
        assert len(colors) == len(durations) == len(messages)

        stages = []
        n = len(durations)
        for i in range(n):
            stages.append(
                ProgressStage(durations[i], messages[i], colors[i], persistent=(i + 1 < n))
            )
        return ProgressDisplay(stages=stages)

    def get_recording_events(self):
        return {
            "hideNextButton": Event(
                is_triggered_by="trialStart",
                js="document.getElementById('next-button').hidden = true",
            ),
            # TODO needed?
            "promptStart": Event(is_triggered_by="trialStart"),
            "recordStart": Event(is_triggered_by="trialStart", delay=MAX_RECORDING_DURATION),
            "playbackRecording": Event(
                is_triggered_by="recordEnd", js="psynet.page.control.playRecording()"
            ),
            "automaticallyContinue": Event(
                is_triggered_by="recordEnd",
                delay=MAX_RECORDING_DURATION + 0.2,
                js="onNextButton();",
            ),
        }

    def get_recording_page(self):
        prompt = Markup(
            f"""
            <small><strong>
            **Remember** Think about the situation of in which the recording could occur and then repeat!
            </strong></small><br>
            {self.definition["txt"]}
            """
        )
        return ModularPage(
            "serial-prosody-recording",
            prompt=AudioPrompt(
                audio=self.definition["url"],
                text=prompt,
            ),
            control=AudioRecordControl(
                duration=MAX_RECORDING_DURATION,
                s3_bucket=S3_BUCKET,
                public_read=True,
                show_meter=True,
                controls=False,
                auto_advance=False,
            ),
            events=self.get_recording_events(),
            progress_display=self.get_recording_progress_display(),
            time_estimate=MAX_RECORDING_DURATION * 3,
        )

    def get_decision_page(self):
        return ModularPage(
            "decision_page",
            prompt=Markup(
                """
                Please select one from the options
                <script>
                psynet.trial.onEvent("trialStart", function(){
                    // Mark the first option as red
                    $('.push-button-container').children()[0].classList.replace('btn-primary', 'btn-danger')

                    // Mark the second option as green
                    $('.push-button-container').children()[1].classList.replace('btn-primary', 'btn-success')
                })

                </script>
                """
            ),
            control=PushButtonControl(["My own recording is bad", "My own recording is correct"]),
            time_estimate=3,
        )

    def show_trial(self, experiment, participant):
        return join(self.get_listen_page, self.get_recording_page, self.get_decision_page)


class SelectTrial(SelectTrialMixin, ImitationChainTrial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        n_targets = len(self.targets)
        target_urls = [
            # TODO to implement
            self.get_target_url(target)
            for target in self.targets
        ]
        labels = ["Recording %d" % (choice + 1) for choice in range(n_targets)]
        js_labels = [label.replace(" ", "_").lower() for label in labels]
        time_estimate = MAX_RECORDING_DURATION * n_targets

        audio_pairs = dict(zip(js_labels, target_urls))

        # Prepare events and stages
        # disable all buttons before start
        events = {
            "hideButtons": Event(
                is_triggered_by="trialStart",
                js="document.getElementsByClassName('push-button-container')[0].hidden = true",
            )
        }
        stages = []
        time_past = 0
        count = 0
        for label in labels:
            # Alternate colors
            color = "blue" if count % 2 == 0 else "red"
            stages.append(
                ProgressStage(MAX_RECORDING_DURATION, Markup(f"Listen to {label}"), color)
            )

            key = "play_" + label
            events[key] = Event(
                is_triggered_by="trialStart",
                delay=time_past,
                js="psynet.audio." + label.replace(" ", "_").lower() + ".play()",
            )
            time_past += MAX_RECORDING_DURATION
            count += 1

        # enable the buttons
        events["showButtons"] = Event(
            is_triggered_by="trialStart",
            delay=time_past,
            js="document.getElementsByClassName('push-button-container')[0].hidden = false",
        )

        return ModularPage(
            "serial-prosody-rating",
            prompt=f"You will listen to {N_CREATORS + 1} recordings. Pick the recording which you find most emotional. Make your choice after listening to all samples.",
            control=PushButtonControl(choices=target_urls, labels=labels),
            time_estimate=time_estimate,
            events=events,
            media=MediaSpec(audio=audio_pairs),
            progress_display=ProgressDisplay(stages=stages),
        )


class CreateAndRateNode(CreateAndRateNodeMixin, AudioImitationChainNode):
    def synthesize_target(self, output_file):
        # TODO: implement
        pass
        # logger.info("******** MOVING THE RECORDING ********: {}".format(self.definition))
        # recording = self.definition[
        #     0
        # ]  # Note that the definition is always a list of len = 1, containing a dictionary
        # TODO migrate to v10
        # download_from_s3(output_file, recording["s3_bucket"], recording["key"])


class CreateAndRateTrialMaker(CreateAndRateTrialMakerMixin, ImitationChainTrialMaker):
    pass


##########################################################################################
# Experiment
##########################################################################################


start_nodes = [
    CreateAndRateNode(
        context={
            "initial_speaker": initial_speaker,
            "sentence_repetition": repetition,
            "txt": txt,
            "initial_audio_file": audio_file,
        }
    )
    for line in STIMULUS_LINES
    for initial_speaker, repetition, txt, audio_file in line.split("|")
]

trial_maker = CreateAndRateTrialMaker(
    n_creators=N_CREATORS,
    n_raters=N_RATERS,
    node_class=CreateAndRateNode,
    creator_class=CreateTrial,
    rater_class=SelectTrial,
    # mixin params
    include_previous_iteration=True,
    rate_mode="select",
    target_selection_method="all",
    verbose=True,  # for the demo
    # trial_maker params
    id_="trial_maker",
    chain_type="across",
    expected_trials_per_participant=len(start_nodes),
    max_trials_per_participant=len(start_nodes),
    start_nodes=start_nodes,
    chains_per_experiment=len(start_nodes),
    balance_across_chains=False,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="n_trials",
    target_n_participants=None,
    wait_for_networks=False,
    max_nodes_per_chain=10,
)

available_demos = ["include_previous_iteration", "rate", "select"]


class Exp(psynet.experiment.Experiment):
    label = "Genetic Algorithm with People"
    initial_recruitment_size = 1
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        setup_experiment(),
        get_instructions(),
        trial_maker,
        SuccessfulEndPage(),
    )
