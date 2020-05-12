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

from math import ceil
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
    join,
    PageMaker
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
)

CONFIG = {
    "mode": "slider",
    "targets": [
        "sunset",
        "eggshell",
        "lavender",
        "lemon",
        "cloud",
        "strawberry",
        "chocolate",
        "grass"
    ],
    "num_practice_trials": 6,
    "num_experiment_trials": 20,
    "proposal_sigma": 50.0, # only relevant for MCMPC and RC
    "trial_maker": {
        "chain_type": "within",
        "num_nodes_per_chain": 6, # note that the final node receives no trials
        "num_chains_per_participant": 4,
        "num_chains_per_experiment": None,  # set to None if chain_type="within"
        "trials_per_node": 1,
        "active_balancing_across_chains": False,
        "check_performance_every_trial": False,
        "propagate_failure": False,
        "recruit_mode": "num_participants",
        "target_num_participants": 10,
        "num_repeat_trials": 6
    }
}
CONFIG["trial_maker"]["time_estimate_per_trial"] = {
    "2afc": 3,
    "slider": 5
}[CONFIG["mode"]]


def make_timeline(config):
    resources = import_resources(config)
    return Timeline(
        resources["instructions"],
        InfoPage(
            f"""
            You will now take {config['num_practice_trials']} practice trials
            to introduce you to the task.
            """,
            time_estimate=5
        ),
        make_practice_trials(resources, config),
        InfoPage(
            f"""
            You will now take {config['num_experiment_trials']} trials
            similar to the ones you just took. Remember to pay careful attention
            in order to get the best bonus!
            """,
            time_estimate=5
        ),
        make_experiment_trials(resources, config),
        SuccessfulEndPage()
    )

def import_resources(config):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=sa_exc.SAWarning)
        mode = config["mode"]
        if mode == "slider":
            from .gibbs import gibbs_factory
            return gibbs_factory(config)
        elif mode == "2afc":
            from .mcmcp import mcmcp_factory
            return mcmcp_factory(config)
        else:
            raise NotImplementedError

def make_practice_trials(resources, config):
    overall_num_trials = config["num_practice_trials"]
    num_trials = ceil(overall_num_trials / 2)
    num_repeats = overall_num_trials - num_trials
    kwargs = {
        **config["trial_maker"],
        "phase": "practice",
        "check_performance_at_end": True,
        "num_trials_per_participant": num_trials,
        "chain_type": "within",
        "num_chains_per_participant": num_trials,
        "active_balancing_across_chains": True,
        "num_repeat_trials": num_repeats
    }
    return make_trial_maker(resources, config, **kwargs)

def make_experiment_trials(resources, config):
    kwargs = {
        **config["trial_maker"],
        "phase": "experiment",
        "check_performance_at_end": True,
        "num_trials_per_participant": config["num_experiment_trials"]
    }
    return make_trial_maker(resources, config, **kwargs)

def make_trial_maker(resources, config, **kwargs):
    return resources["TrialMaker"](
        network_class=resources["Network"],
        trial_class=resources["Trial"],
        node_class=resources["Node"],
        source_class=resources["Source"],
        **kwargs
    )

class Exp(psynet.experiment.Experiment):
    timeline = make_timeline(CONFIG)

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
