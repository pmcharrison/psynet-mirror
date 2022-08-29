import random

import psynet.experiment
from psynet.asset import CachedFunctionAsset, DebugStorage, S3Storage  # noqa
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Module, Timeline, for_loop
from psynet.trial import Node, Trial

from .custom_synth import synth_prosody

##########################################################################################
# Stimuli
##########################################################################################


def synth_stimulus(path, frequencies):
    synth_prosody(vector=frequencies, output_path=path)


NODES = [
    Node(
        definition={
            "frequency_gradient": frequency_gradient,
            "start_frequency": start_frequency,
            "frequencies": [start_frequency + i * frequency_gradient for i in range(5)],
        },
        assets={
            "stimulus": CachedFunctionAsset(
                function=synth_stimulus,
                extension=".wav",
            )
        },
    )
    for frequency_gradient in [-100, -50, 0, 50, 100]
    for start_frequency in [-100, 0, 100]
]


class RateTrial(Trial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage(
            "audio_rating",
            AudioPrompt(
                self.node.assets["stimulus"],
                text="How happy is the following word?",
            ),
            PushButtonControl(
                ["Not at all", "A little", "Very much"],
            ),
        )


audio_ratings = Module(
    "audio_ratings",
    for_loop(
        label="Deliver 5 random samples from the stimulus set",
        iterate_over=lambda nodes: random.sample(nodes, 5),
        logic=lambda node: RateTrial.cue(node),
        time_estimate_per_iteration=RateTrial.time_estimate,
        expected_repetitions=5,
    ),
    nodes=NODES,
)


class Exp(psynet.experiment.Experiment):
    label = "Simple trial demo (2)"
    asset_storage = DebugStorage()
    # asset_storage = S3Storage("psynet-demos", "static-audio")

    timeline = Timeline(
        NoConsent(),
        audio_ratings,
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.trials) == 5
