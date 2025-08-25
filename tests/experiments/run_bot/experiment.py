import tempfile

import psynet.experiment
from psynet.modular_page import (
    AudioRecordControl,
    ModularPage,
    TextControl,
    VideoRecordControl,
)
from psynet.timeline import (
    Timeline,
)


class Exp(psynet.experiment.Experiment):
    label = "Run bot test"

    timeline = Timeline(
        ModularPage(
            "favourite_colour",
            "What's your favourite colour?",
            TextControl(bot_response="red"),
            time_estimate=5,
        ),
        ModularPage(
            "record_audio",
            "Please speak your name into the microphone.",
            AudioRecordControl(
                duration=5.0,
                bot_response_media=lambda bot: generate_text_file(
                    f"This is a recording from {bot.id}!"
                ),
            ),
            time_estimate=5,
        ),
        ModularPage(
            "record_video",
            "We'll now make a recording of your screen and camera.",
            VideoRecordControl(
                duration=5.0,
                recording_source="both",
                show_preview=True,
                controls=True,
                bot_response_media=lambda bot: {
                    "camera": generate_text_file(
                        f"This is a camera recording from bot {bot.id}."
                    ),
                    "screen": generate_text_file(
                        f"This is a screen recording from bot {bot.id}."
                    ),
                },
            ),
            time_estimate=5,
        ),
    )


def generate_text_file(text: str):
    """
    Generates a simple text file to test that the bot can upload files.

    Returns
    -------
    str
        Path to the generated text file.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".txt", delete=False, mode="w", encoding="utf-8"
    ) as tmpfile:
        tmpfile.write(text)
        file_path = tmpfile.name

    return file_path
