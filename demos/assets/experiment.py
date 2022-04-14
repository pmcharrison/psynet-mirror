import requests

import psynet.experiment

from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.timeline import PageMaker, Timeline

from psynet.assets import AssetRegistry, ExternalAsset, ExperimentAsset, LocalStorage


class Exp(psynet.experiment.Experiment):
    name = "Assets demo"


Exp.assets.asset_storage = LocalStorage(root="/Users/peter/psynet-storage")


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
    ),
    ExperimentAsset(
        "config.txt",
        type_="file",
        key="config_variables.txt",
    ),
)


def display_config(experiment):
    text = experiment.assets.get("config_variables.txt").read_text()
    return InfoPage(
        "The following information is pulled from config.txt:\n" + text,
        time_estimate=5,
    )


Exp.timeline = Timeline(
    NoConsent(),
    PageMaker(
        lambda experiment: InfoPage(
            (
                "The following information is pulled from config.txt:\n"
                + experiment.assets.get("config_variables.txt").read_text()
            )
        ),
        time_estimate=5,
    ),
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
