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
from . import templates
from dallinger import db

import psynet.experiment

from psynet.timeline import get_template
from psynet.field import claim_field
from psynet.participant import Participant, get_participant
from psynet.timeline import (
    Page,
    Timeline,
    PageMaker,
    CodeBlock,
    while_loop,
    conditional,
    switch,
    FailedValidation
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    SliderPage,
    NAFCPage,
    NumberInputPage,
    ResponsePage,
    AudioPrompt,
    NullInput
)


##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        ResponsePage(
            "response",
            prompt=AudioPrompt(
                url="/static/audio/bier.wav",
                text="Listen out for someone saying 'bier'."),
            input=NullInput(),
            time_estimate=5
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
