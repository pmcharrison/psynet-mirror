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
    InheritedAssets,
)
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, TextControl
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, PageMaker, Timeline


def slow_computation(path, n, k):
    time.sleep(1)
    x = random.sample(range(n), k)
    with open(path, "w") as f:
        f.write(str(x))


headphone_assets = [
    ExternalS3Asset(
        key="headphone_check/stimulus-1.wav",
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_ISO.wav",
        description="A stimulus for the headphone check",
    ),
    ExternalS3Asset(
        key="headphone_check/stimulus-2.wav",
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_IOS.wav",
        description="A stimulus for the headphone check",
    ),
    ExternalS3Asset(
        key="headphone_check/stimulus-3.wav",
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_SOI.wav",
        description="A stimulus for the headphone check",
    ),
]

misc_assets = [
    CachedFunctionAsset(
        key="slow_computation.txt",
        function=slow_computation,
        arguments=dict(n=200, k=5),
        extension=".txt",
    ),
    ExternalAsset(
        key="psynet-logo.svg",
        url="https://gitlab.com/computational-audition-lab/psynet/-/raw/master/psynet/resources/logo.svg",
        description="The PsyNet Logo",
        variables=dict(dimensions="150x150"),  # broken for some reason
    ),
    ExternalS3Asset(
        key="headphone_check_folder",
        s3_bucket="headphone-check",
        s3_key="",
        description="A folder of stimuli for the headphone check",
    ),
    ExperimentAsset(
        label="config",
        input_path="config.txt",
        key="config_variables.txt",
        description="A file containing configuration variables",
    ),
    CachedAsset(
        label="bier",
        input_path="bier.wav",
        description="A recording of someone saying 'bier'",
    ),
    InheritedAssets("inherited_assets.csv", key="previous_experiment"),
]


def get_config_variables(experiment):
    with open(experiment.assets.get("config_variables.txt").url, "r") as f:
        return f.read()


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
            variables=dict(
                num_characters=len(participant.answer),
                writing_time=participant.last_response.metadata["time_taken"],
            ),
        )
        asset.deposit()


class Exp(psynet.experiment.Experiment):
    label = "Assets demo"
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        headphone_assets,
        misc_assets,
        PageMaker(
            lambda assets: InfoPage(
                Markup(
                    (
                        "<strong>The following information is pulled from config.txt:</strong>\n\n"
                        + assets.get("config_variables.txt").read_text()
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
            PageMaker(
                lambda assets, i=i: ModularPage(
                    f"headphone_check_{i}",
                    AudioPrompt(
                        assets.get(f"headphone_check/stimulus-{i}.wav"),
                        text=f"This is headphone check stimulus number {i}.",
                    ),
                ),
                time_estimate=5,
            )
            for i in range(1, 4)
        ],
        SuccessfulEndPage(),
    )
