# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup

import psynet.experiment
from psynet.modular_page import (
    AudioPrompt,
    Control,
    ModularPage,
    Prompt,
    PushButtonControl,
    TimedPushButtonControl,
    VideoSliderControl,
)
from psynet.page import DebugResponsePage, InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline

##########################################################################################
#### Experiment
##########################################################################################


class HelloPrompt(Prompt):
    macro = "with_hello"
    external_template = "custom-prompts.html"


class ColourText(Control):
    macro = "colour_text_area"
    external_template = "custom-controls.html"

    def __init__(self, colour):
        super().__init__()
        self.colour = colour

    @property
    def metadata(self):
        return {"colour": self.colour}


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
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
                url="/static/audio/bier.wav",
                text="Here is an example of an audio prompt combined with a push button control``.",
            ),
            control=PushButtonControl(["Response A", "Response B"]),
            time_estimate=5,
        ),
        DebugResponsePage(),
        ModularPage(
            "timed_push_button",
            AudioPrompt(
                url="https://headphone-check.s3.amazonaws.com/funk_game_loop.wav",
                text="""
            This page illustrates the timed push button control combined with an audio prompt.
            The submit button is enabled after 3.0 seconds.
            """,
                prevent_response=False,
                start_delay=0.5,
                enable_submit_after=3.0,
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
                """
            This is an example of a custom prompt that adds 'Hello' to every page.
            The custom prompt is defined in the class 'HelloPrompt' and the template
            'custom-prompts.html'. Note that the template inherits from the built-in
            'prompt.simple' macro as defined in PsyNet's 'prompt.html' file.
            """
            ),
            time_estimate=5,
        ),
        ModularPage(
            "example_text_input",
            prompt=Prompt(
                """\
                This is an example of a custom control interface, defined in the class
                'ColourText' and the template 'custom-controls.html'.
                Note how you can customise the background colour by changing the input
                to 'ColourText'.\
            """
            ),
            control=ColourText("aquamarine"),
            time_estimate=5,
        ),
        DebugResponsePage(),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
