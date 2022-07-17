import random
import tempfile
import time

from flask import Markup

import psynet.experiment
from psynet.asset import (
    CachedAsset,
    CachedFunctionAsset,
    ExperimentAsset,
    ExternalAsset,
    ExternalS3Asset,
    InheritedAssets,
    LocalStorage,
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


class Exp(psynet.experiment.Experiment):
    label = "Assets demo"


Exp.assets.asset_storage = LocalStorage(root="/Users/peter/psynet-storage")


Exp.assets.stage(
    CachedFunctionAsset(
        key="slow_computation.txt",
        function=slow_computation,
        arguments=dict(n=200, k=5),
        extension=".txt",
    ),
    ExternalAsset(
        key="psynet-logo.svg",
        url="https://gitlab.com/computational-audition-lab/psynet/-/raw/master/psynet/resources/logo.svg",
        description="The PsyNet logo",
        variables=dict(dimensions="150x150"),  # broken for some reason
    ),
    ExternalS3Asset(
        key="headphone_check/stimulus-1.wav",
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_ISO.wav",
    ),
    ExternalS3Asset(
        key="headphone_check/stimulus-2.wav",
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_IOS.wav",
    ),
    ExternalS3Asset(
        key="headphone_check/stimulus-3.wav",
        s3_bucket="headphone-check",
        s3_key="antiphase_HC_SOI.wav",
    ),
    ExternalS3Asset(
        key="headphone_check_folder",
        s3_bucket="headphone-check",
        s3_key="",
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
    InheritedAssets("inherited_assets.csv", key="previous_experiment")
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
            variables=dict(
                num_characters=len(participant.answer),
                writing_time=participant.last_response.metadata["time_taken"],
            ),
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
