import psynet.experiment

from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt
from psynet.page import ModularPage, SuccessfulEndPage
from psynet.timeline import Timeline

from psynet.assets import ExternalAsset, ExperimentAsset


class Exp(psynet.experiment.Experiment):
    name = "Assets demo"

Exp.assets.register(
    ExternalAsset(
        "https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
        key="headphone_check/stimulus-1.wav"
    ),
    ExternalAsset(
        "https://s3.amazonaws.com/headphone-check/antiphase_HC_IOS.wav",
        key="headphone_check/stimulus-2.wav"
    ),
    ExternalAsset(
        "https://s3.amazonaws.com/headphone-check/antiphase_HC_SOI.wav",
        key="headphone_check/stimulus-3.wav"
    )
)

Exp.timeline = Timeline(
    NoConsent(),
    [
        ModularPage(
            f"headphone_check_{i}",
            AudioPrompt(
                Exp.assets.get(f"headphone_check/stimulus-{i}.wav").url,
                text=f"This is headphone check stimulus number {i}.",
            ),
            time_estimate=5,
        )
        for i in [1, 2, 3]
    ],
    SuccessfulEndPage()
)
