import tempfile

from flask import Markup

import psynet.experiment
from psynet.assets import CachedAsset, ExperimentAsset, ExternalAsset, LocalStorage
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, TextControl
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, PageMaker, Timeline


class Exp(psynet.experiment.Experiment):
    name = "Assets demo"


Exp.assets.asset_storage = LocalStorage(root="/Users/peter/psynet-storage")


Exp.assets.stage(
    ExternalAsset(
        "https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
        key="headphone_check/stimulus-1.wav",
    ),
    ExternalAsset(
        "https://s3.amazonaws.com/headphone-check/antiphase_HC_IOS.wav",
        key="headphone_check/stimulus-2.wav",
    ),
    ExternalAsset(
        "https://s3.amazonaws.com/headphone-check/antiphase_HC_SOI.wav",
        key="headphone_check/stimulus-3.wav",
    ),
    ExperimentAsset(
        "config.txt",
        type_="file",
        key="config_variables.txt",
    ),
    CachedAsset(
        "bier.wav",
        type_="file",
        key="bier.wav",
    ),
    # recreate_assets("recreated_assets.csv")
    # TODO - implement support for loading custom asset specifications (e.g. from previous experiments) (rename cached to persistent)
    # TODO - gracefully deal with the situation of the same asset being created twice
    # TODO - implement export (this should use the key column)
    # TODO - implement S3 support
    # TODO - tests
    # TODO - apply this to static experiments
    # TODO - apply this to audio recording etc
)


def get_config_variables(experiment):
    with open(experiment.assets.get("config_variables.txt").url, "r") as f:
        return f.read()


def save_text(experiment: Exp, participant):
    text = participant.answer
    with tempfile.NamedTemporaryFile("w") as file:
        file.write(text)
        file.flush()
        asset = ExperimentAsset(
            file.name,
            type_="file",
            extension=".txt",
            description="text_box",
            participant_id=participant.id,
        )
        asset.deposit()


Exp.timeline = Timeline(
    NoConsent(),
    PageMaker(
        lambda experiment: InfoPage(
            Markup(
                (
                    "<strong>The following information is pulled from config.txt:</strong>\n\n"
                    + get_config_variables(experiment)
                ).replace("\n", "<br>")
            )
        ),
        time_estimate=5,
    ),
    ModularPage(
        "text_input",
        "Please enter some text. It will be saved to a text file and stored as an experiment asset.",
        TextControl(),
        time_estimate=5,
    ),
    CodeBlock(save_text),
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
    SuccessfulEndPage(),
)
