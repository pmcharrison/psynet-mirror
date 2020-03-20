import random
from sqlalchemy.sql.expression import not_

import dallinger.models
import dallinger.nodes
import dallinger.networks

from ..field import claim_field, claim_var, VarStore
from .main import Trial, TrialNetwork, NetworkTrialGenerator

# pylint: disable=unused-import
import rpdb

class ChainNetwork(TrialNetwork):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_network"}

    head_node_id = claim_field(2, int)
    participant_id = claim_field(3, int)
    id_within_participant = claim_field(4, int)

    chain_type = claim_var("_chain_type")
    trials_per_node = claim_var("_trials_per_node")

    # Note - the <details> slot is occupied by VarStore.

    def __init__(
        self, 
        trial_type, 
        source_class, 
        phase, 
        experiment, 
        chain_type, 
        trials_per_node, 
        participant=None, 
        id_within_participant=None
    ):
        super().__init__(trial_type, phase, experiment)
        experiment.session.add(self)
        experiment.save()

        if participant is not None:
            self.id_within_participant = id_within_participant
            self.participant_id = participant.id

        self.chain_type = chain_type
        self.trials_per_node = trials_per_node
        self.add_source(source_class, experiment, participant)
        
        experiment.save()

    @property
    def head(self):
        if self.head_node_id is None:
            return None
        return dallinger.models.Node.query.filter_by(id=self.head_node_id).one()

    @head.setter
    def head(self, head):
        self.head_node_id = head.id

    def add_node(self, node):
        head = self.head
        if head is not None:
            head.connect(whom=node)
        self.head = node
        if self.num_nodes >= self.max_size:
            self.full = True

    def add_source(self, source_class, experiment, participant=None):
        source = source_class(self, experiment, participant)
        experiment.session.add(source)
        self.add_node(source)
        experiment.save()

    @property
    def source(self):
        return ChainSource.query.filter_by(network_id=self.id).one()

class ChainNode(dallinger.models.Node):
    __mapper_args__ = {"polymorphic_identity": "chain_node"}

    def __init__(self, seed, network, experiment, participant=None):
        # pylint: disable=unused-argument
        super().__init__(network=network, participant=participant)
        self.seed = seed
        self.definition = self.create_definition_from_seed(seed, experiment, participant)

    def create_definition_from_seed(self, seed, experiment, participant):
        raise NotImplementedError

    def create_seed(self, experiment, participant):
        trials = self.completed_trials
        return self.summarise_trials(trials, experiment, participant)

    def summarise_trials(self, trials, experiment, participant):
        raise NotImplementedError

    seed = claim_field(1)
    definition = claim_field(2)

    # VarStore occuppies the <details> slot.
    @property
    def var(self):
        return VarStore(self)

    @property
    def source(self):
        return self.network.source

    @property 
    def phase(self):
        return self.network.phase

    @property 
    def target_num_trials(self):
        return self.network.trials_per_node

    @property 
    def ready_to_spawn(self):
        return self.num_completed_trials >= self.target_num_trials

    @property 
    def query_completed_trials(self):
        return Trial.query.filter_by(
            origin_id=self.id, failed=False, complete=True
        )

    @property 
    def completed_trials(self):
        return self.query_completed_trials.all()

    @property
    def num_completed_trials(self):
        return self.query_completed_trials.count()

    @property
    def num_viable_trials(self):
        return Trial.query.filter_by(origin_id=self.id, failed=False).count()

class ChainSource(dallinger.nodes.Source):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_source"}

    ready_to_spawn = True
    seed = claim_field(1)

    @property
    def var(self): # occupies the <details> attribute
        return VarStore(self)

    def __init__(self, network, experiment, participant):
        super().__init__(network, participant)
        self.seed = self.generate_seed(network, experiment, participant)

    def create_seed(self, experiment, participant):
        # pylint: disable=unused-argument
        return self.seed

    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError
        

class ChainTrial(Trial):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_trial"}

    @property
    def source(self):
        return self.origin.source

    @property 
    def phase(self):
        return self.origin.phase

class ChainTrialGenerator(NetworkTrialGenerator):
    def __init__(
        self,  
        source_class,
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
        check_performance_every_trial,
        network_class=ChainNetwork,
        node_class=ChainNode
    ):
        assert chain_type in ["within", "across"]

        if chain_type == "across" and num_trials_per_participant > num_chains_per_experiment:
            raise ValueError(
                "In across-chain experiments, <num_trials_per_participant> "
                "cannot exceed <num_chains_per_experiment>."
            )

        self.node_class = node_class
        self.source_class = source_class
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
        for i in range(self.num_chains_per_participant):
            self.create_network(experiment, participant, id_within_participant=i)

    def create_networks_across(self, experiment):
        for _ in range(self.num_chains_per_experiment):
            self.create_network(experiment)

    def create_network(self, experiment, participant=None, id_within_participant=None):
        network = self.network_class(
            trial_type=self.trial_type,
            source_class=self.source_class,
            phase=self.phase,
            experiment=experiment,
            chain_type=self.chain_type,
            trials_per_node=self.trials_per_node,
            participant=participant,
            id_within_participant=id_within_participant
        )
        experiment.session.add(network)
        experiment.save()
        return network
    
    def on_complete(self, experiment, participant):
        pass

    def find_networks(self, participant, experiment):
        if self.get_num_completed_trials_in_phase(participant) >= self.num_trials_per_participant:
            return []

        networks = self.network_class.query.filter_by(
            trial_type=self.trial_type,
            phase=self.phase,
            full=False
        )

        if self.chain_type == "within":
            networks = self.filter_by_participant_id(networks, participant)
        elif self.chain_type == "across":
            networks = self.exclude_participated(networks, participant)

        networks = networks.all()

        if self.active_balancing_across_chains:    
            networks.sort(key=lambda network: network.num_complete_trials)
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
        if head.ready_to_spawn:
            seed = head.create_seed(participant, experiment)
            node = self.node_class(seed, network, experiment, participant)
            experiment.session.add(node)
            network.add_node(node)

    def find_node(self, network, participant, experiment): 
        head = network.head
        if head.num_viable_trials >= self.trials_per_node:
            return None
        return head

    def finalise_trial(self, answer, trial, experiment, participant):
        super().finalise_trial(answer, trial, experiment, participant)
        self.add_to_participated_networks(participant, trial.network_id)
