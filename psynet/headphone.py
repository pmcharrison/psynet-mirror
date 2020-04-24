from .timeline import Module

from .trial.non_adaptive import (
    NonAdaptiveNetwork,
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec
)

from .modular_page import(
    ModularPage,
    AudioPrompt,
    NAFCControl
)

def get_stimulus_set(media_url: str = "https://s3.amazonaws.com/headphone-test"):
    return StimulusSet(
        StimulusSpec(
            definition={
                "label": label,
                "answer": answer,
                "url": f"{media_url}/{answer}"
            },
            phase="test"
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
    )

    class HeadphoneTrial(NonAdaptiveTrial):
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
                time_estimate=7.5
            )
