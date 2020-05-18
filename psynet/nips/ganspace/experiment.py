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
    NumberInputPage,
    NAFCPage,
    TextInputPage
)
from psynet.ishihara import colour_blind_test
from psynet.colour_vocab import colour_vocab_test

CONFIG = {
    "mode": "gsp",
    "ganspace_server": "http://54.204.210.121:5000",
    "targets": [
        "trustworthy",
        "beautiful",
        "innocent"
    ],
    "num_dimensions": 5,
    "num_practice_trials": 6,
    "num_experiment_trials": 20,
    "slider_sigma": 2.0,
    "trial_maker": {
        "chain_type": "within",
        "num_nodes_per_chain": 31, # note that the final node receives no trials
        "num_chains_per_participant": 1,
        "num_chains_per_experiment": None,  # set to None if chain_type="within"
        "trials_per_node": 1,
        "active_balancing_across_chains": False,
        "check_performance_every_trial": False,
        "propagate_failure": False,
        "recruit_mode": "num_participants",
        "target_num_participants": 10,
        "num_repeat_trials": 6,
        "time_estimate_per_trial": 7.5,
        "wait_for_networks": True
    }
}

demographics = join(
    InfoPage(
        "First we need to ask some quick questions about you.",
        time_estimate=5
    ),
    NumberInputPage(
        label='age',
        prompt='What is your age, in years?',
        time_estimate=5
    ),
    NAFCPage(
        label='gender',
        prompt='With what gender do you most identify yourself?',
        time_estimate=5,
        choices=['Male', 'Female', 'Other'],
        arrange_vertically=True
    ),
    NAFCPage(
        label='education',
        prompt='What is your highest educational qualification?',
        time_estimate=7,
        choices=['None', 'Elementary school', 'Middle school', 'High school', 'Bachelor', 'Master', 'PhD'],
        arrange_vertically=True
    ),
    TextInputPage(
        "country",
        "What country are you from?",
        time_estimate=5,
        one_line=True
    ),
    TextInputPage(
        "mother_tongue",
        "What is your mother tongue?",
        time_estimate=5,
        one_line=True
    )
)

final_questionnaire = join(
    TextInputPage(
        "strategy",
        """
        Please tell us in a few words about your experience taking the task.
        What was your strategy?
        Did you find the task easy or difficult?
        Did you find it interesting or boring?
        """,
        time_estimate=20,
        one_line=False
    ),
    TextInputPage(
        "technical",
        """
        Did you experience any technical problems during the task?
        If so, please describe them.
        """,
        time_estimate=10,
        one_line=False
    )
)

def make_timeline(config):
    resources = import_resources(config)
    return Timeline(
        # demographics,
        # colour_vocab_test(),
        # colour_blind_test(),
        # resources["instructions"],
        InfoPage(
            f"""
            You will now take {config['num_practice_trials']} practice trials
            to introduce you to the task.
            """,
            time_estimate=5
        ),
        # make_practice_trials(resources, config),
        # InfoPage(
        #     f"""
        #     You will now take
        #     {config['num_experiment_trials'] + config['trial_maker']['num_repeat_trials']}
        #     trials similar to the ones you just took. Remember to pay careful attention
        #     in order to get the best bonus!
        #     """,
        #     time_estimate=5
        # ),
        make_experiment_trials(resources, config),
        final_questionnaire,
        SuccessfulEndPage()
    )

def import_resources(config):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=sa_exc.SAWarning)
        mode = config["mode"]
        if mode == "gsp":
            from gibbs import gibbs_factory
            return gibbs_factory(config)
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
        "chain_type": "across",
        "num_chains_per_experiment": num_trials,
        "active_balancing_across_chains": False,
        "trials_per_node": 1e9,
        "num_nodes_per_chain": 10,
        "num_repeat_trials": num_repeats,
        "recruit_mode": "num_participants",
        "target_num_participants": 0
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
