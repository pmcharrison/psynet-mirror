import random
import json
from statistics import mean
from typing import Optional
from collections import Counter

from sqlalchemy import String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast, not_

import dallinger.models
import dallinger.nodes
import dallinger.networks

from ..field import claim_field
from .main import Trial, NetworkTrialGenerator

# pylint: disable=unused-import
import rpdb

class ChainTrial(Trial):
    __mapper_args__ = {"polymorphic_identity": "chain_trial"}

    phase = claim_field(3, str)


class ChainTrialGenerator(NetworkTrialGenerator):
    def __init__(
        self,  
        trial_class, 
        phase,
        time_allotted_per_trial,
        chain_type,
        num_trials_per_participant,
        num_chains_per_participant,
        num_chains_per_experiment,
        responses_per_node,
        active_balancing_across_chains,
        check_performance_at_end,
        check_performance_every_trial
    ):
        assert chain_type in ["within", "across"]

        self.trial_class = trial_class
        self.phase = phase
        self.time_allotted_per_trial = time_allotted_per_trial
        self.chain_type = chain_type
        self.num_trials_per_participant = num_trials_per_participant
        self.num_chains_per_participant = num_chains_per_participant
        self.num_chains_per_experiment = num_chains_per_experiment
        self.responses_per_node = responses_per_node
        self.active_balancing_across_chains = active_balancing_across_chains
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial

        super().__init__(
            trial_class, 
            network_class=ChainNetwork,
            phase=phase,
            time_allotted_per_trial=time_allotted_per_trial, 
            expected_num_trials=num_trials_per_participant,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial
        )
    
    def init_participant(self, experiment, participant):
        super().init_participant(experiment, participant)
        self.init_participated_networks(participant) # how many times can a participant visit the same network? 1 or Inf, lets say
    
    #### Participated networks
    def init_participated_networks(self, participant):
        participant.set_var(self.with_namespace("participated_networks"), [])

    def get_participated_networks(self, participant):
        return participant.get_var(self.with_namespace("participated_networks"))

    def add_to_participated_networks(self, participant, network_id):
        networks = self.get_participated_networks(participant)
        networks.append(network_id)
        participant.set_var(self.with_namespace("participated_networks"), networks)

    def experiment_setup_routine(self, experiment):
        if self.count_networks() == 0:
            self.create_networks(experiment)

    def create_networks(self, experiment):
        if self.chain_type == "across":
            for _ in range(self.num_chains_per_experiment):
                self.create_network(experiment)

    def create_network(self, experiment):
        network = self.network_class(
            trial_type=self.trial_type,
            phase=self.phase,
            experiment=experiment
        )
        experiment.session.add(network)
    
    def on_complete(self, experiment, participant):
        pass
    
    def finalise_trial(self, answer, trial, experiment, participant):
        # super().finalise_trial(answer, trial, experiment, participant)
        # self.increment_completed_stimuli_in_phase_and_block(participant, trial.block, trial.stimulus_id)
        # self.increment_num_completed_trials_in_phase(participant)
        # trial.stimulus.num_completed_trials += 1
        pass

class ChainNetwork(dallinger.networks.Chain):
    __mapper_args__ = {"polymorphic_identity": "chain_network"}

# class AcrossChainTrialGenerator(ChainTrialGenerator):
#     def __init__(
#         self,  
#         trial_class, 
#         network_class,
#         phase,
#         time_allotted_per_trial,
#         num_trials_per_participant,
#         num_chains_per_experiment,
#         responses_per_node=1,
#         active_balancing_across_chains=False,
#         check_performance_at_end=False,
#         check_performance_every_trial=False
#     ):
#         super().__init__(
#             trial_class, 
#             network_class=AcrossChainNetwork,
#             phase=phase,
#             time_allotted_per_trial=time_allotted_per_trial, 
#             expected_num_trials=num_trials_per_participant,
#             check_performance_at_end=check_performance_at_end,
#             check_performance_every_trial=check_performance_every_trial
#         )
#         self.num_chains_per_experiment = num_chains_per_experiment

#     def self.create_networks(self, experiment):
#         raise NotImplementedError

# class WithinChainTrialGenerator(ChainTrialGenerator):
#     def __init__(
#         self,  
#         trial_class, 
#         network_class,
#         phase,
#         time_allotted_per_trial,
#         num_trials_per_participant,
#         num_chains_per_participant,
#         responses_per_node=1,
#         active_balancing_across_chains=False,
#         check_performance_at_end=False,
#         check_performance_every_trial=False
#     ):
#         super().__init__(
#             trial_class, 
#             network_class=WithinChainNetwork,
#             phase=phase,
#             time_allotted_per_trial=time_allotted_per_trial, 
#             expected_num_trials=num_trials_per_participant,
#             check_performance_at_end=check_performance_at_end,
#             check_performance_every_trial=check_performance_every_trial
#         )
#         self.num_chains_per_participant = num_chains_per_experiment

#     def self.create_networks(self, experiment):
#         raise NotImplementedError