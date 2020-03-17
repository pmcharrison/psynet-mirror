import random
from sqlalchemy.sql.expression import not_

import dallinger.models
import dallinger.nodes
import dallinger.networks

from ..field import claim_field
from .main import Trial, TrialNetwork, NetworkTrialGenerator

# pylint: disable=unused-import
import rpdb


class ChainTrialGenerator(NetworkTrialGenerator):
    def __init__(
        self,  
        node_class,
        trial_class, 
        phase,
        time_allotted_per_trial,
        chain_type,
        num_trials_per_participant,
        num_chains_per_participant,
        num_chains_per_experiment,
        trials_per_node,
        active_balancing_across_chains,
        check_performance_at_end,
        check_performance_every_trial
    ):
        assert chain_type in ["within", "across"]

        self.node_class = node_class
        self.trial_class = trial_class
        self.phase = phase
        self.time_allotted_per_trial = time_allotted_per_trial
        self.chain_type = chain_type
        self.num_trials_per_participant = num_trials_per_participant
        self.num_chains_per_participant = num_chains_per_participant
        self.num_chains_per_experiment = num_chains_per_experiment
        self.trials_per_node = trials_per_node
        self.active_balancing_across_chains = active_balancing_across_chains
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial

        if chain_type == "within":
            network_class = WithinChainNetwork 
        elif chain_type == "across":
            network_class = AcrossChainNetwork

        super().__init__(
            trial_class, 
            network_class=network_class,
            phase=phase,
            time_allotted_per_trial=time_allotted_per_trial, 
            expected_num_trials=num_trials_per_participant,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial
        )
    
    def init_participant(self, experiment, participant):
        super().init_participant(experiment, participant)
        self.init_participated_networks(participant)
        if self.chain_type == "within":
            self.create_networks_within(experiment, participant)
    
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
        if self.count_networks() == 0 and self.chain_type == "across":
            self.create_networks_across(experiment)

    def create_networks_within(self, experiment, participant):
        for _ in range(self.num_chains_per_participant):
            self.create_network_within(experiment, participant)

    def create_networks_across(self, experiment):
        for _ in range(self.num_chains_per_experiment):
            self.create_network_across(experiment)

    def create_network_within(self, experiment, participant):
        network = self.network_class(
            trial_type=self.trial_type,
            phase=self.phase,
            experiment=experiment,
            participant=participant
        )
        experiment.session.add(network)

    def create_network_across(self, experiment):
        network = self.network_class(
            trial_type=self.trial_type,
            phase=self.phase,
            experiment=experiment
        )
        experiment.session.add(network)
    
    def on_complete(self, experiment, participant):
        pass

    def find_networks(self, participant, experiment):
        networks = self.network_class.query.filter_by(
            trial_type=self.trial_type,
            phase=self.phase,
            full=False
        )
        if self.chain_type == "within":
            networks = self.filter_by_participant_id(networks, participant)
        elif self.chain_type == "across":
            networks = self.exclude_participated(networks, participant)

        if self.active_balancing_across_chains:    
            networks.sort(key=lambda network: network.num_nodes)
        else:
            random.shuffle(networks)

        return networks

    @staticmethod
    def filter_by_participant_id(networks, participant):
        return networks.filter_by(participant_id=participant.id)

    def exclude_participated(self, networks, participant):
        return networks.filter(
            not_(self.network_class.id.in_(self.get_participated_networks(participant)))
        )
    
    def grow_network(self, network, participant, experiment):
        head = network.head
        if head.num_successful_trials(self.trial_class) >= self.trials_per_node:
            node = self.create_node(head.get_successful_trials(self.trial_class), network, participant, experiment)
            experiment.session.add(node)
            network.add_node(node, self.node_class)

    def create_node(self, trials, network, participant, experiment):
        raise NotImplementedError

    def find_node(self, network, participant, experiment): 
        return network.head

    def finalise_trial(self, answer, trial, experiment, participant):
        super().finalise_trial(answer, trial, experiment, participant)
        self.add_to_participated_networks(participant, trial.network_id)

class ChainNetwork(TrialNetwork):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_network"}

    head_node_id = claim_field(2, int)

    def get_head(self):
        if self.head_node_id is None:
            return None
        return ChainNode.query.filter_by(id=self.head_node_id)

    def set_head(self, head):
        self.head_node_id = head.id

    def add_node(self, node):
        head = self.get_head()
        if head is not None:
            head.connect(whom=node)
        self.set_head(node)
        if self.num_nodes >= self.max_size:
            self.full = True

class WithinChainNetwork(ChainNetwork):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "within_chain_network"}

    participant_id = claim_field(3, int)
    
    def __init__(self, trial_type, phase, experiment, participant):
        super().__init__(trial_type, phase, experiment)
        self.participant_id = participant.id
        self.add_source(experiment, participant)

    def add_source(self, experiment, participant):
        source = self.new_source(experiment, participant)
        experiment.session.add(source)
        self.add_node(source)

    def new_source(self, experiment, participant):
        raise NotImplementedError

class AcrossChainNetwork(ChainNetwork):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "across_chain_network"}

    def __init__(self, trial_type, phase, experiment):
        super().__init__(trial_type, phase, experiment)
        self.add_source(experiment)

    def add_source(self, experiment):
        source = self.new_source(experiment)
        experiment.session.add(source)
        self.add_node(source)

    def new_source(self, experiment):
        raise NotImplementedError

class ChainNode(dallinger.models.Node):
    __mapper_args__ = {"polymorphic_identity": "chain_node"}

    def query_successful_trials(self, trial_class):
        return trial_class.query.filter_by(
            origin_id=self.id, failed=False, complete=True
        )

    def get_successful_trials(self, trial_class):
        return self.query_successful_trials(trial_class).all()

    def num_successful_trials(self, trial_class):
        return self.query_successful_trials(trial_class).count()

class ChainTrial(Trial):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_trial"}

    @property 
    def phase(self):
        return self.origin.phase
