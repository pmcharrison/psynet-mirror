# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

import random
import re
import time
from statistics import mean
from typing import List, Union

from dallinger import db
from flask import Markup

import psynet.experiment
from psynet.field import claim_field
from psynet.page import (
    DebugResponsePage,
    InfoPage,
    SuccessfulEndPage,
    VolumeCalibration,
)
from psynet.participant import Participant, get_participant
from psynet.prescreen import HeadphoneCheck
from psynet.timeline import Timeline, get_template, join

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        VolumeCalibration(),
        HeadphoneCheck(),
        InfoPage(
            "You passed the headphone screening task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
