"""
This is a simple experiment that allows participants to rate sounds on a scale of 1 to 5.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring

from pathlib import Path

import psynet.experiment
from psynet.asset import asset  # noqa
from psynet.modular_page import ModularPage, RatingControl
from psynet.page import InfoPage
from psynet.timeline import Event, MediaSpec, Timeline
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

N_TRIALS_PER_PARTICIPANT = 10


def get_nodes():
    stimuli = list_stimuli()
    return [
        StaticNode(
            definition={
                "stimulus_a": stimulus_a["name"],
                "stimulus_b": stimulus_b["name"],
            },
        )
        for stimulus_a in stimuli
        for stimulus_b in stimuli
        if stimulus_a["name"] != stimulus_b["name"]
    ]


def get_assets():
    stimuli = list_stimuli()
    return {
        stimulus["name"]: asset(
            stimulus["path"],
            extension=".mp3",
            cache=True,  # reuse the uploaded file between deployments
        )
        for stimulus in stimuli
    }


def list_stimuli():
    stimulus_dir = Path("data/instrument_sounds")
    return [
        {
            "name": path.stem,
            "path": path,
        }
        for path in list(stimulus_dir.glob("*.mp3"))
    ]


# Run `python3 experiment.py` to list the stimuli.
if __name__ == "__main__":
    stimuli = list_stimuli()
    print(f"Found {len(stimuli)} stimuli:")
    for stimulus in stimuli:
        print(f"- {stimulus['name']}")


class CustomTrial(StaticTrial):
    time_estimate = 10

    def show_trial(self, experiment, participant):
        return ModularPage(
            "ratings",
            "Please listen to Sound A and Sound B and rate their similarity on a scale from 1 to 5.",
            RatingControl(
                values=5,
                min_description="Not at all similar",
                max_description="Very similar",
            ),
            events={
                "submitEnable": Event(is_triggered_by="promptEnd"),
            },
            time_estimate=10,
            media=MediaSpec(
                audio={
                    "stimulus_a": self.assets["stimulus_a"],
                    "stimulus_b": self.assets["stimulus_b"],
                }
            ),
            events={
                "playStimulusA": Event(
                    is_triggered_by="trialStart",
                    js="psynet.audio.stimulus_a.play();",
                    message="Sound A",
                    message_color="blue",
                ),
                "silence": Event(
                    is_triggered_by="audioFinished: stimulus_a",
                    message="",
                ),
                "playStimulusB": Event(
                    is_triggered_by="silence",
                    delay=0.5,
                    js="psynet.audio.stimulus_b.play();",
                    message="Sound B",
                    message_color="blue",
                ),
                "responseEnable": Event(
                    is_triggered_by="audioFinished: stimulus_b",
                    delay=0.0,
                ),
                "submitEnable": Event(
                    is_triggered_by="responseEnable",
                    delay=0.0,
                ),
            },
        )


class Exp(psynet.experiment.Experiment):
    label = "Subjective rating"

    timeline = Timeline(
        InfoPage(
            """
            In this experiment you will hear some sounds. Your task will be to rate
            them on a scale of 1 to 5 on several scales.
            """,
            time_estimate=5,
        ),
        StaticTrialMaker(
            id_="ratings",
            trial_class=CustomTrial,
            nodes=get_nodes,
            expected_trials_per_participant=N_TRIALS_PER_PARTICIPANT,
            assets=get_assets,
        ),
        InfoPage(
            """
            Thank you for your participation!
            """,
            time_estimate=5,
        ),
    )
