# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

import logging
import rpdb
import random
import re
import time
import os
import warnings

from typing import Union, List
from dallinger import db
from flask import Markup
from statistics import mean
from sqlalchemy import exc as sa_exc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import psynet.experiment
from psynet.timeline import (
    Timeline,
    join
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
)

CONFIG = {
    "targets": ["tree", "rock", "carrot", "banana"]
}

def make_timeline(config):
    return Timeline(
        make_trial_maker(config),
        SuccessfulEndPage()
    )

def import_classes(config):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=sa_exc.SAWarning)
        from .gibbs import gibbs_factory
        return gibbs_factory(config)

def make_trial_maker(config):
    classes = import_classes(config)
    return classes["TrialMaker"](
        network_class=classes["Network"],
        trial_class=classes["Trial"],
        node_class=classes["Node"],
        source_class=classes["Source"],
        phase="experiment",  # can be whatever you like
        time_estimate_per_trial=5,
        chain_type="across",  # can be "within" or "across"
        num_trials_per_participant=4,
        num_nodes_per_chain=6, # note that the final node receives no trials
        num_chains_per_participant=None,  # set to None if chain_type="across"
        num_chains_per_experiment=4,  # set to None if chain_type="within"
        trials_per_node=1,
        active_balancing_across_chains=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        propagate_failure=False,
        recruit_mode="num_participants",
        target_num_participants=10,
        num_repeat_trials=3
    )

class Exp(psynet.experiment.Experiment):
    timeline = make_timeline(CONFIG)

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
