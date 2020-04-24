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

from psynet.timeline import get_template, join
from psynet.field import claim_field
from psynet.participant import Participant, get_participant
from psynet.timeline import (
    Timeline
)
from psynet.headphone import headphone_check
from psynet.page import SuccessfulEndPage, InfoPage, DebugResponsePage

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        headphone_check(),
        InfoPage("You passed the headphone screening task! Congratulations.", time_estimate=3),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
