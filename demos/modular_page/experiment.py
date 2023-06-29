# pylint: disable=unused-import,abstract-method,unused-argument,no-member

from typing import Union

from markupsafe import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import (
    AudioPrompt,
    Control,
    ModularPage,
    Prompt,
    PushButtonControl,
    TimedPushButtonControl,
    VideoSliderControl,
)
from psynet.page import DebugResponsePage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import NoArgumentProvided


class HelloPrompt(Prompt):
    macro = "with_hello"
    external_template = "custom-prompts.html"

    def __init__(
        self,
        username: str,
        text: Union[None, str, Markup] = None,
        text_align: str = "left",
    ):
        super().__init__(text=text, text_align=text_align)
        self.username = username


class ColorText(Control):
    macro = "color_text_area"
    external_template = "custom-controls.html"

    def __init__(self, color, bot_response=NoArgumentProvided):
        super().__init__(bot_response=bot_response)
        self.color = color

    @property
    def metadata(self):
        return {"color": self.color}

    def get_bot_response(self, experiment, bot, page, prompt):
        return "Hello, I am a bot!"


class Exp(psynet.experiment.Experiment):
    label = "Modular page demo"

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "text", prompt="This is an example of a simple text page.", time_estimate=5
        ),
        ModularPage(
            "text",
            prompt=Markup(
                "This is an example of a text page with some <strong>simple formatting</strong>."
            ),
            time_estimate=5,
        ),
        ModularPage(
            "response",
            prompt=AudioPrompt(
                audio="/static/audio/bier.wav",
                text="Here is an example of an audio prompt combined with a push button control``.",
            ),
            control=PushButtonControl(["Response A", "Response B"]),
            time_estimate=5,
        ),
        DebugResponsePage(),
        ModularPage(
            "timed_push_button",
            AudioPrompt(
                audio="https://headphone-check.s3.amazonaws.com/funk_game_loop.wav",
                text="""
            This page illustrates the timed push button control combined with an audio prompt.
            """,
            ),
            TimedPushButtonControl(choices=["A", "B", "C"], arrange_vertically=False),
            time_estimate=5,
        ),
        DebugResponsePage(),
        ModularPage(
            "video_slider",
            prompt="This is an example of a video slider page.",
            control=VideoSliderControl(
                url="https://psynet.s3.amazonaws.com/video-slider.mp4",
                file_type="mp4",
                width="400px",
                height="400px",
                reverse_scale=True,
                directional=False,
            ),
            time_estimate=5,
        ),
        DebugResponsePage(),
        ModularPage(
            "example_hello",
            prompt=HelloPrompt(
                username="stranger",
                text="""
                    This is an example of a custom prompt that adds 'Hello' to every page.
                    The custom prompt is defined in the class 'HelloPrompt' and the template
                    'custom-prompts.html'. Note that the template inherits from the built-in
                    'prompt.simple' macro as defined in PsyNet's 'prompt.html' file.
                    """,
            ),
            time_estimate=5,
        ),
        ModularPage(
            "example_text_input",
            prompt=Prompt(
                """\
                This is an example of a custom control interface, defined in the class
                'ColorText' and the template 'custom-controls.html'.
                Note how you can customise the background color by changing the input
                to 'ColorText'.\
            """
            ),
            control=ColorText("aquamarine"),
            time_estimate=5,
        ),
        DebugResponsePage(),
        SuccessfulEndPage(),
    )
