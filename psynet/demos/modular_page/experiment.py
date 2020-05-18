# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
from statistics import mean
import random
import re
from typing import Union, List
import time
from dallinger import db

import psynet.experiment

from psynet.timeline import get_template
from psynet.field import claim_field
from psynet.participant import Participant, get_participant
from psynet.timeline import (
    Timeline
)
from psynet.page import SuccessfulEndPage, InfoPage, DebugResponsePage
from psynet.modular_page import (
    ModularPage,
    Prompt,
    AudioPrompt,
    Control,
    NAFCControl,
    VideoSliderControl
)


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
        return {
            "colour": self.colour
        }

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        ModularPage(
            "text",
            prompt="This is an example of a simple text page.",
            time_estimate=5
        ),
        ModularPage(
            "text",
            prompt=Markup("This is an example of a text page with some <strong>simple formatting</strong>."),
            time_estimate=5
        ),
        ModularPage(
            "video_slider",
            prompt="This is an example of a video slider page.",
            control=VideoSliderControl(
                url="https://psynet.s3.amazonaws.com/video-slider.mp4",
                file_type="mp4",
                width="300px",
                height="300px"
            ),
            time_estimate=5
        ),
        ModularPage(
            "example_hello",
            prompt=HelloPrompt("""
            This is an example of a custom prompt that adds 'Hello' to every page.
            The custom prompt is defined in the class 'HelloPrompt' and the template
            'custom-prompts.html'. Note that the template inherits from the built-in
            'prompt.simple' macro as defined in PsyNet's 'prompt.html' file.
            """),
            time_estimate=5
        ),
        ModularPage(
            "example_text_input",
            prompt=Prompt("""\
                This is an example of a custom control interface, defined in the class
                'ColourText' and the template 'custom-controls.html'.
                Note how you can customise the background colour by changing the input
                to 'ColourText'.\
            """),
            control=ColourText("aquamarine"),
            time_estimate=5
        ),
        DebugResponsePage(),
        ModularPage(
            "response",
            prompt=AudioPrompt(
                url="/static/audio/bier.wav",
                text="Here is an example of an audio prompt combined with an NAFC control."
            ),
            control=NAFCControl(["Response A", "Response B"]),
            time_estimate=5
        ),
        DebugResponsePage(),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
