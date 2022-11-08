import random
import tempfile
import time

from flask import Markup

import psynet.experiment
from psynet.asset import (
    CachedAsset,
    CachedFunctionAsset,
    DebugStorage,
    ExperimentAsset,
    ExternalAsset,
    ExternalS3Asset,
)
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, TextControl
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, Module, PageMaker, Timeline


def slow_computation(path, n, k):
    time.sleep(1)
    x = random.sample(range(n), k)
    with open(path, "w") as f:
        f.write(str(x))


headphone_assets = {
    "stimulus_1": ExternalS3Asset(
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_ISO.wav",
        description="A stimulus for the headphone check",
    ),
    "stimulus_2": ExternalS3Asset(
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_IOS.wav",
        description="A stimulus for the headphone check",
    ),
    "stimulus_3": ExternalS3Asset(
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_SOI.wav",
        description="A stimulus for the headphone check",
    ),
}

misc_assets = {
    "slow_computation": CachedFunctionAsset(
        local_key="slow_computation.txt",
        function=slow_computation,
        arguments=dict(n=200, k=5),
        extension=".txt",
    ),
    "psynet_logo": ExternalAsset(
        url="https://gitlab.com/computational-audition-lab/psynet/-/raw/master/psynet/resources/logo.svg",
        description="The PsyNet Logo",
    ),
    "headphone_check_folder": ExternalS3Asset(
        s3_bucket="headphone-check",
        s3_key="",
        description="A folder of stimuli for the headphone check",
    ),
    "config": ExperimentAsset(
        input_path="config.txt",
        description="A file containing configuration variables",
    ),
    "bier": CachedAsset(
        input_path="bier.wav",
        description="A recording of someone saying 'bier'",
    ),
}


def save_text(participant):
    text = participant.answer
    with tempfile.NamedTemporaryFile("w") as file:
        file.write(text)
        file.flush()
        asset = ExperimentAsset(
            label="text_input",
            input_path=file.name,
            extension=".txt",
            description="Some text that the participant filled out",
            parent=participant,
        )
        asset.deposit()


class Exp(psynet.experiment.Experiment):
    label = "Assets demo"
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        Module(
            "headphone_check",
            [
                PageMaker(
                    lambda assets, i=i: ModularPage(
                        f"headphone_check_{i}",
                        AudioPrompt(
                            assets[f"stimulus_{i}"],
                            text=f"This is headphone check stimulus number {i}.",
                        ),
                    ),
                    time_estimate=5,
                )
                for i in range(1, 4)
            ],
            assets=headphone_assets,
        ),
        Module(
            "misc",
            PageMaker(
                lambda assets: InfoPage(
                    Markup(
                        (
                            "<strong>The following information is pulled from config.txt:</strong>\n\n"
                            + assets["config"].read_text()
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
            assets=misc_assets,
        ),
        SuccessfulEndPage(),
    )
